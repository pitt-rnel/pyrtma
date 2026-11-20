@ECHO OFF
REM pyrtma msg_defs.py compiling
python -m pyrtma.compile -i ./msg_defs/example.defs -o ./msg_defs/ -n example_messages --py