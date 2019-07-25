#!/bin/bash

script_dir=`dirname $0`
script_dir=`cd $script_dir; pwd`
vsc_dir=$script_dir

for i in 1 2; do
  vsc_dir=`dirname $vsc_dir`
done

export PYTHONPATH=${vsc_dir}/src:/project/fun/portaskela/boolector/inst/lib

python3 -m unittest ${@:1}

