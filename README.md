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

### Create a message in message.yaml

Message definitions are created in a .yaml file.

The ruamel.yaml parser library is used internally (<https://yaml.readthedocs.io/en/latest/>)

Notes about yaml format:

- Whitespace sensitive. Use either 2 or 4 spaces for tab not '\t'
- Key-values must be separated by a colon followed by a space, (Key: Value, not Key:Value)
- Must follow the top-level headers shown below.
- Unused sections should be marked `null`
- Names must start with letter. (no _ or numeric prefixes allowed)
- Use **(.yaml)** extension not **(.yml)**

List of supported native data types:

- char
- unsigned char
- byte
- int
- signed int
- unsigned int
- short
- unsigned short
- long
- signed long
- unsigned long
- long long
- signed long long
- unsigned long long
- float
- double
- int8
- uint8
- int16
- uint16
- int32
- uint32
- int64
- uint64

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

    # A block of message ids can be reserved by a file for future use
    # Ranges are inclusive on both ends
    _RESERVED_:
        id: [1000, 1002:1005, 1006 - 1008, 1009 to 1012]
```

Run the following command to compile the yaml file into Python, C, Matlab, or Javascript files. This will output a message.(py|h|m|js) file.

```shell
python -m pyrtma.compile -i examples/msg_defs/message.yaml --py --c --mat --js
```

The msg_defs directory should now have message def files created for each language.

The rtma objects are compiled into objects suitable for each language.

## Examples

See [`/examples/example.py`](https://github.com/pitt-rnel/pyrtma/blob/master/examples/example.py) for pub/sub demo app

Compile the example message defintions:

```shell
python -m pyrtma.compile -i ./examples/msg_defs/message.yaml --py
```

Start the demo MessageManager server

```shell
python -m pyrtma.manager
```

Start the publisher in one console:

```shell
python ./examples/example.py --pub
```

Start the subscriber in another:

```shell
python ./examples/example.py --sub
```
