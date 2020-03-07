
import os
import sys
import subprocess
from pylint import run_pylint

scripts_dir = os.path.dirname(os.path.abspath(__file__))
vsc_dir = os.path.dirname(scripts_dir)


sys.argv = [sys.argv[0]]

sys.argv.append("-E")
sys.argv.append("--extension-pkg-whitelist=pyboolector")
sys.argv.append("--disable=missing-super-argument")
sys.argv.append("--load-plugins")
sys.argv.append("vsc.pylint")
sys.argv.append(os.path.join(vsc_dir, "src", "vsc"))
#for f in os.listdir(os.path.join(vsc_dir, "ve", "unit")):
#    if f.startswith("test_"):
#        sys.argv.append(os.path.join(vsc_dir, "ve", "unit", f))

#for a in sys.argv:
#    print("Argument: " + str(a))

run_pylint()

print("PyLint Complete")

