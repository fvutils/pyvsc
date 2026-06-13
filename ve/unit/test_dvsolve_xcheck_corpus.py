"""Phase F / F-0b — validate the XCHECK soak-corpus manifest.

`ve/xcheck_corpus.txt` is the checked-in real-workload corpus the `xcheck-soak`
CI job runs under `VSC_SOLVER=dv-solve VSC_DVSOLVE_XCHECK=1` (the F-4 default-flip
gate). This test does NOT run the corpus (CI does) — it guards the *manifest* so it
cannot silently rot: every listed path must exist, there are no duplicates, the
corpus is non-empty, and the documented exclusions (the dv-solve meta-tests) are
honored. A renamed/deleted corpus test then fails here loudly instead of silently
dropping out of the soak gate.
"""
import os
import unittest


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_MANIFEST = os.path.join(_REPO_ROOT, "ve", "xcheck_corpus.txt")


def _corpus_entries():
    """Parse the manifest into a list of (lineno, path) for the real entries
    (comments and blank lines stripped)."""
    entries = []
    with open(_MANIFEST) as fp:
        for lineno, raw in enumerate(fp, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            entries.append((lineno, line))
    return entries


class TestDvSolveXCheckCorpus(unittest.TestCase):

    def test_manifest_exists(self):
        self.assertTrue(os.path.isfile(_MANIFEST),
                        "XCHECK corpus manifest missing: %s" % _MANIFEST)

    def test_corpus_non_empty(self):
        self.assertTrue(_corpus_entries(),
                        "XCHECK corpus manifest has no test entries")

    def test_every_entry_exists(self):
        missing = [(ln, p) for ln, p in _corpus_entries()
                   if not os.path.isfile(os.path.join(_REPO_ROOT, p))]
        self.assertEqual(
            missing, [],
            "XCHECK corpus references missing files (renamed/deleted?): %s"
            % missing)

    def test_no_duplicates(self):
        paths = [p for _ln, p in _corpus_entries()]
        dupes = sorted({p for p in paths if paths.count(p) > 1})
        self.assertEqual(dupes, [], "duplicate corpus entries: %s" % dupes)

    def test_excludes_dvsolve_meta_tests(self):
        # The dv-solve meta-tests toggle env / reset the fallback tally / nest
        # XCHECK — they are not "real workload" and must stay out of the soak
        # corpus (documented exclusion in the manifest header).
        meta = [p for _ln, p in _corpus_entries()
                if os.path.basename(p).startswith("test_dvsolve_")]
        self.assertEqual(
            meta, [],
            "dv-solve meta-tests must not be in the XCHECK soak corpus: %s" % meta)


if __name__ == "__main__":
    unittest.main()
