#!/bin/bash

script_dir=`dirname $0`
script_dir=`cd $script_dir; pwd`
vsc_dir=$script_dir

for i in 1 2; do
  vsc_dir=`dirname $vsc_dir`
done

export PYTHONPATH=${vsc_dir}/src

# valgrind --tool=memcheck --suppressions=./valgrind-python.supp ${vsc_dir}/packages/python/bin/python3 -m unittest ${@:1}
# valgrind --tool=memcheck python3 -m unittest ${@:1}
# gdb --args python3 -m unittest ${@:1}
#PREF="gdb --args "
#PREF="valgrind --tool=memcheck"
$PREF ${vsc_dir}/packages/python/bin/python3 -m unittest ${@:1}

