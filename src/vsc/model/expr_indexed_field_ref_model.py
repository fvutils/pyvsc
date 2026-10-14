

# Created on Mar 6, 2020
#
# @author: ballance

from vsc.model.expr_model import ExprModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel

class ExprIndexedFieldRefModel(ExprModel):
    """Indexed-path mechanism to access a field"""
    
    def __init__(self,
                 root : ExprModel,
                 idx_t):
        super().__init__()
        
        if not isinstance(root, (ExprFieldRefModel,ExprArraySubscriptModel,ExprIndexedFieldRefModel)):
            raise Exception("unsupported root for an indexed reference: " + str(root))
        
        self.root = root
        self.idx_t = idx_t
        
    def get_target(self, root=None):
        if root is not None:
            ret = root
        elif isinstance(self.root, ExprArraySubscriptModel):
            ret = self.root.subscript()
        elif isinstance(self.root, ExprIndexedFieldRefModel):
            from vsc.visitors.expr2field_visitor import Expr2FieldVisitor
            fm = Expr2FieldVisitor().field(self.root)
            ret = fm
        else:
            ret = self.root.fm

        for i in self.idx_t:
            ret = ret.get_field(i)

        return ret
        
        
    def build(self, btor, ctx_width=-1):
        alts = ref_alternatives(self)
        if is_symbolic(alts):
            return build_select(btor, alts)
        t = alts[0][1]
        ret = t.build(btor)
        if ret is None:
            raise Exception("Expression %s produced null node" % str(t))
        return ret
    
    def is_signed(self):
        return ref_alternatives(self)[0][1].is_signed
    
    def width(self):
        return ref_alternatives(self)[0][1].width
    
    def accept(self, v):
        v.visit_expr_indexed_fieldref(self)
        
    def val(self, parent=None): 
        return self.get_target().val
        

def ref_alternatives(e, is_sym=None):
    """Every field a reference chain may name, as ``[(conds, field)]``.

    A chain is a field reference, an array subscript or an indexed field
    reference (``objs[i].sub.v``, ``objs[i].arr[j]``) over one another. A
    subscript whose index the solver chooses (``is_sym``, by default "reads
    a used-rand field") has no value until the solve, so it is not read: the
    chain names one field per element, and ``conds`` lists the
    ``(index_expr, k)`` pairs that select it. A chain with no such index
    yields its one field with no conditions.
    """
    from vsc.model.expr_fieldref_model import ExprFieldRefModel
    from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel
    if is_sym is None:
        from vsc.visitors.refs_used_rand_visitor import refs_used_rand
        is_sym = refs_used_rand
    if isinstance(e, ExprFieldRefModel):
        return [((), e.fm)]
    if isinstance(e, ExprIndexedFieldRefModel):
        ret = []
        for conds, f in ref_alternatives(e.root, is_sym):
            for i in e.idx_t:
                f = f.get_field(i)
            ret.append((conds, f))
        return ret
    if isinstance(e, ExprArraySubscriptModel):
        ret = []
        sym = is_sym(e.rhs)
        for conds, arr in ref_alternatives(e.lhs, is_sym):
            if sym:
                for k, f in enumerate(arr.field_l):
                    ret.append((conds + ((e.rhs, k),), f))
            else:
                index = int(e.rhs.val())
                if index >= len(arr.field_l):
                    raise Exception("List size: %d index: %d" % (
                        len(arr.field_l), index))
                ret.append((conds, arr.field_l[index]))
        if len(ret) == 0:
            raise Exception("Variable index into an empty array")
        return ret
    raise Exception("unsupported reference: " + str(e))


def is_symbolic(alts):
    """True when ``ref_alternatives`` found an index the solver chooses."""
    return len(alts) > 1 or len(alts[0][0]) > 0


def index_exprs(alts):
    """The distinct index expressions the alternatives' conditions read."""
    ret = []
    for conds, _ in alts:
        for ie, _ in conds:
            if not any(ie is x for x in ret):
                ret.append(ie)
    return ret


def build_select(btor, alts):
    """Boolector term for a symbolic reference: the first alternative whose
    index conditions hold, ``c0 ? f0 : c1 ? f1 : ... : f_last``. As for a
    scalar ``arr[idx]``, an index out of range reads the last alternative."""
    idx_m = {}
    def eq(ie, k):
        key = id(ie)
        if key not in idx_m:
            idx_m[key] = ie.build(btor)
        idx = idx_m[key]
        if k >= (1 << idx.width):
            return None         # the index cannot reach this element
        return btor.Eq(idx, btor.Const(k, idx.width))
    reach = []
    for conds, f in alts:
        terms = [eq(ie, k) for ie, k in conds]
        if any(t is None for t in terms):
            continue
        reach.append((terms, f))
    ret = reach[-1][1].build(btor)
    for terms, f in reversed(reach[:-1]):
        c = terms[0]
        for t in terms[1:]:
            c = btor.And(c, t)
        ret = btor.Cond(c, f.build(btor), ret)
    return ret
