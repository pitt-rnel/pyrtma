import pyrtma
import climber_message

for mdf in pyrtma.msg_defs.values():
    in_msg = mdf.from_random()
    in_str = in_msg.to_json()
    out_msg = mdf.from_json(in_str)
    out_str = out_msg.to_json()

    if pyrtma.is_equal(in_msg, out_msg) or in_str != out_str:
        print(f"{mdf.type_name:<32} -> Pass")
    else:
        print(f"{mdf.type_name:<32} -> Fail")
        break
