python -m pyrtma.compile -i src/pyrtma/core_defs/core_defs.yaml -o src/pyrtma/ --py
python -m pyrtma.compile -i examples/msg_defs/example_messages.yaml -o examples/msg_defs/ --py
python -m pyrtma.compile -i tests/test_msg_defs/test_defs.yaml -o tests/test_msg_defs/ --py --mat