# pyrtma

[![Python package](https://github.com/pitt-rnel/pyrtma/actions/workflows/python-package.yml/badge.svg)](https://github.com/pitt-rnel/pyrtma/actions/workflows/python-package.yml)
[![Documentation Status](https://readthedocs.org/projects/pyrtma/badge/?version=latest)](https://pyrtma.readthedocs.io/en/latest/?badge=latest)

RTMA/Dragonfly client written in python with no external dependencies. Based on and compatible with [Dragonfly Messaging](https://github.com/pitt-rnel/rnel_dragonfly)

## Installation

pyrtma is [available on PyPI](https://pypi.org/project/pyrtma/)

```shell
pip install pyrtma --upgrade
```

### Installing for pyrtma development

This is only necessary for individuals who would like to contribute to pyrtma.

From pyrtma git repo directory:
```shell
pip install --upgrade pip setuptools
pip install -e .
```

## Usage

### Launch Manager

```shell
python -m pyrtma.manager
```
or
```shell
message_manager
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

- `char`
- `byte`
- `float`
- `double`
- `int8`
- `int16`
- `int32`
- `int64`
- `uint8`
- `uint16`
- `uint32`
- `uint64`

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
    AGE_TYPE: int32

# Non-message structured data (no id field)
struct_defs:
    TEST_STRUCT:
        fields:
            value_str: char[STR_SIZE]
            value_int: int32

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
    # Note that ':' cannot be used to indicate a range, as this will cause
    # the yaml parser to throw an error
    _RESERVED_:
        id: [1000, 1002 - 1008, 1009 to 1012]
```

Run the following command to compile the yaml file into Python, C, Matlab, or Javascript files. This will output a message.(py|h|m|js) file.

```shell
python -m pyrtma.compile -i examples/msg_defs/message.yaml --py --c --mat --js
```
or
```shell
rtma_compiler -i examples/msg_defs/message.yaml --py --c --mat --js
```

The msg_defs directory should now have message def files created for each language.

The rtma objects are compiled into objects suitable for each language.

### Message Definitions in Clients

`pyrtma.Client` decodes messages using a `MessageDefinitions` instance.

A simple mental model:

1. Compile your YAML schema into a Python defs file.
2. Load that defs file in your application.
3. Pass the loaded definitions into each `Client` you create.

For predictable behavior, pass definitions explicitly.

Example: import from compiled defs module

```python
import pyrtma
import my_project_defs

client = pyrtma.Client(name="MY_MODULE", definitions=my_project_defs)
```
or 

```
defs = my_project_defs.get_message_definitions()
client = pyrtma.Client(name="MY_MODULE", definitions=defs)
```

Example: load from a standalone defs object from a file path

```python
import pyrtma

defs = pyrtma.load_message_definitions("./msg_defs/my_project_defs.py")
```

The same definitions object also carries the common lookup helpers:

```python
msg_cls = client.get_msg_cls(1234)
msg_name = defs.message_name_from_id(1234)
msg_id = defs.message_id_from_name("MY_MESSAGE")
module_name = client.module_name_from_id(212)
module_id = defs.module_id_from_name("MY_MODULE")
```

Use `Client` when you already have a running client and want lookups tied to its active schema. Use `MessageDefinitions` when you only need schema access.

### How Client Definition Detection Works

When `definitions` is not passed, `Client` resolves the schema in a priority order.

Definition resolution flow:

1. If you passed a `MessageDefinitions` object or a module object with compiled definitions, that wins immediately.
2. If `definitions=None`, `Client` checks the `PYRTMA_MSGDEF_MODULES` environment variable first.
   - This value is a semicolon-separated list of module names, for example: `PYRTMA_MSGDEF_MODULES=my_project_defs;other_defs`
   - It checks each named module only if it is already loaded in `sys.modules`.
   - The first loaded module that looks like compiled pyrtma defs (it has `COMPILED_PYRTMA_VERSION` and `get_message_definitions()`) is used.
   - If none are found, it emits a warning and falls back to the next step below.
3. If the environment variable is unset or no matching module is found, `Client` optionally auto-detects from the current process.
   - It starts from the bundled core definitions and scans already-imported non-`pyrtma` modules.
   - It uses the first one that exposes the compiled pyrtma definition API.
4. If auto-detect is disabled or nothing is found, it falls back to the bundled core definitions.

This means the precedence is:

`explicit definitions` > `PYRTMA_MSGDEF_MODULES` > `auto-detect` > `core_defs`

Guidance:

- Use explicit `definitions=` in production applications.
- Set `PYRTMA_MSGDEF_MODULES` when you want a predictable, process-wide default without passing the schema every time.
- Auto-detect is convenient for quick development and local scripting.
- Set `auto_detect=False` to skip the scan and use core definitions unless you pass `definitions` explicitly.

>[!NOTE]
>The pyrtma message compiler requires python 3.10+. Messages compiled for python in python 3.10+ may continue to work with pyrtma clients in older versions of python, but those versions are being phased out.

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

# Javascript
Clients in javascript require the web_manager server to convert websocket messages to rtma messages.

Run:
```shell 
python -m pyrtma.web_manager -m <MM_IP> -p <WEBSOCKET_PORT> -d <DEFS_FILE>
```
or
```shell 
web_manager -m <MM_IP> -p <WEBSOCKET_PORT> -d <DEFS_FILE>
```
to launch the web_manager which will listen to websocket connects on port <WEBSOCKET_PORT> and forward to message manager at <MM_IP>, using pyrtma message definitions defined in <DEFS_FILE>.

See [rtma-js](https://github.com/pitt-rnel/rtma-js) for developing rtma clients in javascript.

# DataLogger

See `examples/data_log_example.py` for an example on how to configure data collection for a DataLogger.

To start up the logging module:
```shell
python -m pyrtma.data_logger --help
```

or

```shell
data_logger --help
```

There is also an interactive command line tool to control and configure the DataLogger manually:

```shell
python -m pyrtma.data_logger.cli
```