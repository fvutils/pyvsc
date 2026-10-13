"""pytest config for the vsc.sphinx suite.

The introspection tests need only vsc; the build tests need Sphinx and are
skipped without it. Test projects live under roots/test-<name>; the fixture
classes they document are in vsc_doc_fixture.py (this directory is put on
sys.path so the builds can import it).
"""
import os
import sys
from pathlib import Path

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    import sphinx  # noqa: F401
except ImportError:  # pragma: no cover
    collect_ignore = ["test_sphinx_build.py", "test_sphinx_elaborate.py"]
else:
    pytest_plugins = ["sphinx.testing.fixtures"]


@pytest.fixture(scope="session")
def rootdir():
    return Path(HERE) / "roots"
