"""
Example 2 — arrays (fixed & random size), foreach, and weighted dist.

Run:  PYTHONPATH=src python examples/dc/02_arrays_dist.py
"""
import vsc.dc as vdc


@vdc.dataclass
class Pkt(vdc.RandClass):
    # Fixed-size array of 8 bytes.
    payload: list[vdc.u8] = vdc.rand(size=8)
    # Random-size array: constrain .size in the constraint.
    tags: list[vdc.u8] = vdc.rand(max_size=8)
    kind: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        # Each payload byte is an ASCII lowercase letter. Constraint bodies are a
        # declarative subset (not executed), so use literals — 0x61='a', 0x7a='z'
        # — rather than calls like ord('a').
        with vdc.foreach(self.payload) as it:
            it >= 0x61
            it <= 0x7a
        # Random-size bounds.
        self.tags.size > 2
        self.tags.size <= 6
        # Weighted distribution over kind.
        vdc.dist(self.kind, [
            vdc.weight(0, 10),
            vdc.weight((1, 3), 80),
            vdc.weight(4, 10),
        ])


def main():
    pkt = Pkt()
    for _ in range(5):
        pkt.randomize()
        assert all(ord('a') <= b <= ord('z') for b in pkt.payload)
        assert 2 < len(pkt.tags) <= 6
        word = "".join(chr(b) for b in pkt.payload)
        print(f"payload={word}  #tags={len(pkt.tags)}  kind={pkt.kind}")


if __name__ == "__main__":
    main()
