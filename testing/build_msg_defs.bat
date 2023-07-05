@ECHO OFF
REM pyrtma msg_defs.py compiling
python -m pyrtma.compile -i climber_config.h -o ./msg_defs/test_defs --c --py --js --mat