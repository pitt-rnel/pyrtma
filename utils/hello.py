import pyrtma
import pyrtma.core_defs as cd
import uuid
import time


def main():
    client = pyrtma.Client(module_id=0, name="hello_test")
    client.connect()
    client.subscribe([cd.MT_HELLO, cd.MT_GOODBYE])
    set_name = cd.MDF_CLIENT_SET_NAME()

    uid = uuid.uuid4().hex[:8]
    set_name.name = f"hello_{uid}"
    client.send_message(set_name)

    client.send_signal(cd.MT_INTRODUCE)

    last_send = time.time()
    interval = 1.0
    pong = cd.MDF_PONG()
    try:
        while True:
            msg = client.read_message(timeout=0.100)

            if msg:
                print(str(msg.data))

            if (now := time.time()) - last_send > interval:
                client.send_message(pong)
                last_send = now

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
