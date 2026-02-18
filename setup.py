
import os
from setuptools import setup, find_namespace_packages

def get_version():
    try:
        import ivpm
        return ivpm.get_pkg_version(__file__)
    except:
        return "0.0.0"

setup(
  name="pyvsc",
  version=get_version(),
#  packages=find_packages(include=['vsc', 'vsc.*']),
  packages=find_namespace_packages(where='src'),
  package_dir={'' : 'src'},
  author="Matthew Ballance",
  author_email="matt.ballance@gmail.com",
  description=("pyvsc (Verification Stimulus and Coverage) is a Python package for generating randomized stimulus and defining and collecting functional coverage."),
  long_description="""
  PyVSC implements a Python-embedded domain-specific language for
  capturing random variables and data structures, constraints,
  and functional coverage metrics. PyVSC is built on top of the
  Boolector SMT solver. 
  """,
  license="Apache 2.0",
  keywords = ["Python", "Functional Verification", "Constraints", "Coverage"],
  url = "https://github.com/fvutils/pyvsc",
  entry_points={
    'console_scripts': [
      'vsc = vsc.__main__:main'
    ]
  },
  setup_requires=[
    'setuptools_scm',
    'ivpm',
  ],
  install_requires=[
    'pyboolector>=3.2.2',
    'pyucis>=0.1.4',
    'toposort'
  ],
  python_requires='>=3.10',
)

