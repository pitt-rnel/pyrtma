# labswitchboard -> websocket server

import asyncio, websockets, json, ctypes, sys

sys.path.append("../../")

import pyrtma

# Choose a unique message type id number
MT_SINE_TEST_MSG = 9000

# Create a user defined message from a ctypes.Structure or basic ctypes
@pyrtma.msg_def
class SINE_TEST_MSG(pyrtma.MessageData):
    _fields_ = [("time", ctypes.c_double), ("value", ctypes.c_double)]

    type_id: int = MT_SINE_TEST_MSG
    type_name: str = "SINE_TEST_MSG"


async def rtma_ws(websocket):
    print("starting rtma_ws coroutine")
    # Setup Client
    try:
        mod = pyrtma.Client()
        mod.connect()  # this should ideally be an "await" statement

        # Select the messages to receive
        mod.subscribe([MT_SINE_TEST_MSG])  # this should ideally be an "await" statement
    except:
        return

    data = {"time": [], "value": []}
    while True:
        try:
            msg = mod.read_message(
                timeout=0
            )  # this should REALLY be an "await" statement
            if msg is not None and msg.name == "SINE_TEST_MSG":
                data["time"] = msg.data.time
                data["value"] = msg.data.value
                await websocket.send(json.dumps(data))
            else:
                await asyncio.sleep(0.01)
        except websockets.ConnectionClosedOK:
            break
        except:
            break


async def main():
    print("starting main")
    async with websockets.serve(rtma_ws, "localhost", 5678):
        await asyncio.Future()  # run forever


print("calling run")
asyncio.run(main())
