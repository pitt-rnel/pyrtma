#!/bin/sh
# The standard benchmark suite: one publisher with 0, 1 and 5 subscribers, at
# 128, 1024 and 8192 bytes, 5 runs each. Extra arguments go to every run,
# such as --start-manager, or -s HOST:PORT for a manager that is running.
here=$(dirname "$0")
echo "pyrtma benchmark suite"
echo
for subscribers in 0 1 5; do
    for size in 128 1024 8192; do
        python "$here/pyrtma_bench.py" -n 10000 -np 1 -ns "$subscribers" -ms "$size" -r 5 "$@"
        echo
    done
done
