
import os
import ivpm
from setuptools import setup

setup(
  name="pyvsc",
  version=ivpm.get_pkg_version(__file__),
  packages=['vsc'],
  package_dir={'' : 'src'},
  author="Matthew Ballance",
  author_email="matt.ballance@gmail.com",
  description=("pyvsc (Verification Stimulus and Coverage) is a Python package for generating randomized stimulus and defining and collecting functional coverage."),
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
    'pyboolector',
  ],
)

