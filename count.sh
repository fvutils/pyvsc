#!/bin/sh

files="$files `find src/vsc2 -name '*.py'`"
files="$files `find packages/libvsc/src -name '*.cpp'`"
files="$files `find packages/libvsc/src -name '*.h'`"

cat $files | wc -l

