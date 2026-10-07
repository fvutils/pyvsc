"""The workload registry (design §4.1).

A workload is a class holding one definition of a randomization problem per
front-end, a list of the fields that make up a sample, and a `check` oracle:

    @workload
    class Alu(Workload):
        name, family = "alu", "scalar"
        fields = ("op", "a", "b")
        def classic(vsc): ...          # returns a @vsc.randobj class
        def dc(vdc): ...               # returns a @vdc.dataclass class
        def cr(cr): ...                # returns a constrainedrandom RandObj class
        def check(s): ...              # plain Python over {field: int | list}

The builders take the module they need as an argument and import nothing at
module scope, so this registry loads in the parent without pyvsc, and each
child builds its classes against whichever pyvsc its PYTHONPATH holds. A
front-end a workload can't express is left as None: that cell is `n/a`.

`check` shares no code with pyvsc, so a fast-but-wrong arm can't win. The
manifest records a hash of each workload's source, so editing a constraint
breaks the trend line visibly instead of silently comparing a new problem
with an old one.
"""
from __future__ import annotations

import hashlib
import importlib
import inspect

FAMILIES = ("scalar", "distribution", "composite", "arrays")
_MODULES = ("scalar", "distribution", "composite", "arrays")

REGISTRY: dict = {}


class Workload:
    name: str = ""
    family: str = ""
    rev: int = 1                  # bump on a deliberate semantic change
    fields: tuple = ()
    classic = None
    dc = None
    cr = None

    @staticmethod
    def check(s: dict) -> bool:
        raise NotImplementedError


def workload(cls):
    if not cls.name or cls.family not in FAMILIES:
        raise ValueError(f"workload {cls.__name__}: needs a name and a family in {FAMILIES}")
    if cls.name in REGISTRY:
        raise ValueError(f"workload {cls.name} registered twice")
    REGISTRY[cls.name] = cls
    return cls


def _load():
    if not REGISTRY:
        for m in _MODULES:
            importlib.import_module(f"{__name__}.{m}")


def get(name: str):
    _load()
    return REGISTRY[name]


def all_workloads() -> dict:
    _load()
    return dict(REGISTRY)


def source_sha(cls) -> str:
    return hashlib.sha256(inspect.getsource(cls).encode()).hexdigest()[:16]


def frontends(cls) -> list:
    return [fe for fe in ("classic", "dc", "cr") if getattr(cls, fe) is not None]
