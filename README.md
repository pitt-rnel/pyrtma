# pyrtma

[![Python package](https://github.com/pitt-rnel/pyrtma/actions/workflows/python-package.yml/badge.svg)](https://github.com/pitt-rnel/pyrtma/actions/workflows/python-package.yml)
[![Documentation Status](https://readthedocs.org/projects/pyrtma/badge/?version=latest)](https://pyrtma.readthedocs.io/en/latest/?badge=latest)

RTMA/Dragonfly client written in python with no external dependencies. Based on and compatible with [Dragonfly Messaging](https://github.com/pitt-rnel/rnel_dragonfly)

## Installation

pyrtma is [available on PyPI](https://pypi.org/project/pyrtma/)

```shell
pip install pyrtma
```

### Installing for pyrtma development

This is only necessary for individuals who would like to contribute to pyrtma.

```shell
pip install --upgrade pip setuptools
pip install -e .
```

## Usage

### Launch Manager

```shell
python -m pyrtma.manager -a "127.0.0.1"
```

### Create a message in message.h

Message definitions are created in a .yaml file.

```yaml
# message.yaml

imports: null

constants: 
    STR_SIZE: 32

string_constants: null

host_ids: null

module_ids:
    PERSON_PUBLISHER: 112
    PERSON_SUBSCRIBER: 113

struct_defs: null

message_defs:
    PERSON_MESSAGE:
        id: 1234
        fields:
            name: char[STR_SIZE]
            age: int
    ANOTHER_EXAMPLE:
        id: 5678
        fields:
            value_str: char[STR_SIZE]
            value_int: int
            value_float: float
            value_double: double
```

Run the following command to compile the yaml file into Python, C, Matlab, or Javascript files. This will output a message.(py|h|m|js) file.

```shell
python -m pyrtma.compile -i msg_defs/message.yaml --py --c --mat --js
```

Below shows the python class objects output for the user defined messages in message.yaml

```python

@pyrtma.msg_def
class PERSON_MESSAGE(pyrtma.MessageData):
    _fields_ = [
        ("name", ctypes.c_char * 32),
        ("age", ctypes.c_int)
    ]
    type_id = 1234
    type_name = "PERSON_MESSAGE"
    type_hash = "76f148a9"


MDF_PERSON_MESSAGE = PERSON_MESSAGE


@pyrtma.msg_def
class ANOTHER_EXAMPLE(pyrtma.MessageData):
    _fields_ = [
        ("value_str", ctypes.c_char * 32),
        ("value_int", ctypes.c_int),
        ("value_float", ctypes.c_float),
        ("value_double", ctypes.c_double)
    ]
    type_id = 5678
    type_name = "ANOTHER_EXAMPLE"
    type_hash = "3b377f5a"


MDF_ANOTHER_EXAMPLE = ANOTHER_EXAMPLE

```

### Create a publisher module in publisher.py

```python
# publisher.py
import message
import pyrtma
import time

mod = pyrtma.Client(module_id=message.MID_PERSON_PUBLISHER)

# Connect to the manager
mod.connect(server_name="127.0.0.1:7111")

# Create an instance of the person message and populate with data
msg = message.MDF_PERSON_MESSAGE()
msg.name = "Alice"  # str gets converted to c_char
msg.age = 42

# Send the person message every second
while True:
    print("Sending message")
    mod.send_message(msg)
    time.sleep(1)
```

### Create a subscriber module in subscriber.py

```python
# subscriber.py
import message
import pyrtma

# Keeping module_id blank makes Manager dynamically create a module id.
# This is default behavior.
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
            if msg.type_id == message.MDF_PERSON_MESSAGE.type_id:
                name = msg.data.name  # c_char get converted to str
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
python publisher.py
```

### Launch the subscriber

You should see the message 'Hello my name is Alice and I am 42 years old' print in your shell

```shell
python subscriber.py
```
