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

Notes about yaml format:

- Whitespace sensitive. Use either 2 or 4 spaces for tab not '\t'
- Must follow the top-level headers shown below.
- Unused sections should be marked `null`
- Use **(.yaml)** extension not **(.yml)**

Below is an example:

```yaml
# message.yaml

imports: null

# Constant values and expressions
constants: 
    STR_SIZE: 32
    LONG_STRING: STR_SIZE * 2

# Constant string values
string_constants:
    default_msg: "hello_world"

host_ids: null

module_ids:
    PERSON_PUBLISHER: 212
    PERSON_SUBSCRIBER: 214

# Alias a type by another name
aliases:
    AGE_TYPE: int

# Non-message structured data (no id field)
struct_defs:
    TEST_STRUCT:
        fields:
            value_str: char[STR_SIZE]
            value_int: int

# Message defintions with user assigned id field
message_defs:
    PERSON_MESSAGE:
        id: 1234
        fields:
            name: char[STR_SIZE]
            age: AGE_TYPE

    ANOTHER_EXAMPLE:
        id: 5678
        fields:
            value_struct: TEST_STRUCT
            value_float: float
            value_double: double

    # Example signal definition
    USER_SIGNAL:
        id: 2468
        fields: null

    # Example using a nested message defintion 
    PERSON_LIST:
        id: 1357
        fields:
            person: PERSON_MESSAGE[32]

    # Example reusing a message definition by another name
    EMPLOYEES:
        id: 1368
        fields: PERSON_LIST
```

Run the following command to compile the yaml file into Python, C, Matlab, or Javascript files. This will output a message.(py|h|m|js) file.

```shell
python -m pyrtma.compile -i examples/msg_defs/message.yaml --py --c --mat --js
```

The msg_defs directory should now have message def files created for each language.

The rtma objects are compiled into objects suitable for each language.

## Example Pub/Sub

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
python examples/publisher.py
```

### Launch the subscriber

You should see the message 'Hello my name is Alice and I am 42 years old' print in your shell

```shell
python examples/subscriber.py
```
