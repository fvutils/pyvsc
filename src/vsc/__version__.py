import os

# The single source of pyvsc's version. pyproject.toml reads _pkg_version, and
# the release job checks that the v* tag equals BASE. CI stamps SUFFIX on every
# non-tag build (see .github/workflows/ci.yml); a tag build leaves it empty.
BASE = "1.0.0"
SUFFIX = ""

__version__ = (BASE, SUFFIX)

# Used by pyproject.toml dynamic versioning
_pkg_version = BASE + SUFFIX


def get_version():
    """Return the full version string, using git describe when in a source tree."""
    base, suffix = __version__
    version = base + suffix

    src_dir = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    git_dir = os.path.join(src_dir, ".git")

    if os.path.isdir(git_dir):
        try:
            import subprocess
            out = subprocess.check_output(
                ["git", "describe", "--tags", "--dirty", "--always"],
                cwd=src_dir,
                stderr=subprocess.DEVNULL,
            ).decode().strip()
            if out != "v" + base:
                return "%s+%s" % (version, out)
        except Exception:
            pass

    return version
