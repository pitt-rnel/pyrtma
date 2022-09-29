# pyrtma [![Python package](https://github.com/pitt-rnel/pyrtma/actions/workflows/python-package.yml/badge.svg)](https://github.com/pitt-rnel/pyrtma/actions/workflows/python-package.yml)
RTMA/Dragonfly client written in python with no external dependencies. Based on and compatible with [Dragonfly Messaging](https://github.com/pitt-rnel/rnel_dragonfly)

## Installation
pyrtma is [available on PyPI](https://pypi.org/project/pyrtma/)
```shell
$ pip install pyrtma
```
## Usage

### Launch Manager
```shell
$ python -m pyrtma.manager -a "127.0.0.1"
```

### Create a message in message.py

```python
import ctypes
import pyrtma

MT_PERSON_MESSAGE = 1234


@pyrtma.msg_def
class PERSON_MESSAGE(pyrtma.MessageData):
    _fields_ = [
        ("name", ctypes.c_byte * 32),  # String data type (32 bits)
        ("age", ctypes.c_uint32),  # Unsigned integer (32 bits)
    ]

    type_id: int = MT_PERSON_MESSAGE
    type_name: str = "PERSON_MESSAGE"

    def read_str(self, field: str) -> str:
        """Helper function for reading strings"""
        ctype = getattr(self, field)
        return bytearray(ctype).decode()

    def write_str(self, field: str, value: str):
        """Helper function for writing strings"""
        byte_value = value.encode()
        attr = getattr(self, field)
        attr[: len(byte_value)] = byte_value
```

### Create a publisher module in publisher.py
```python
import message
import pyrtma
import time

mod = pyrtma.Client()

# Connect to the manager
mod.connect(server_name="127.0.0.1:7111")

# Create an instance of the person message and populate with data
msg = message.PERSON_MESSAGE()
msg.write_str("name", "Alice")  # use our helper function
msg.age = 42

# Send the person message every second
while True:
    print("Sending message")
    mod.send_message(msg)
    time.sleep(1)
```

Create a subscriber module in subscriber.py
```python
import message
import pyrtma

mod = pyrtma.Client()

# Connect to the manager
mod.connect(server_name="127.0.0.1:7111")

# Subscribe to the person message and pyrtma's exit message (when manager is closed)
mod.subscribe([message.MT_PERSON_MESSAGE, pyrtma.MT_EXIT])

while True:
    try:
        # Read a message. We can specify a time. -1 means it will block until
        # a message is received
        msg = mod.read_message(timeout=-1)
        if msg is not None:

            # Find out what kind of message we received
            # We can check the message id
            if msg.type_id == message.PERSON_MESSAGE.type_id:
                name = msg.data.read_str("name")  # use our helper function
                age = msg.data.age
                print(f"Hello my name is {name} and I am {age} years old")

            # Or we can check the message name
            elif msg.name == "EXIT":
                print("Goodbye.")
                break

    except KeyboardInterrupt:
        break
```

### Launch the publisher
```shell
$ python publisher.py
```

### Launch the subscriber
You should see the message 'Hello my name is Alice and I am 42 years old' print in your shell
```shell
$ python subscriber.py
```