#!/bin/bash
python -m pyrtma.compile -i src/pyrtma/core_defs/rtma.defs -o src/pyrtma/ -n core_defs --py
python -m pyrtma.compile -i examples/msg_defs/example.defs -o examples/msg_defs/ -n examples_messages --py
python -m pyrtma.compile -i tests/test_msg_defs/test.defs -o tests/test_msg_defs/ -n test_defs --py --mat