# pyrtma [![Python package](https://github.com/pitt-rnel/pyrtma/actions/workflows/python-package.yml/badge.svg)](https://github.com/pitt-rnel/pyrtma/actions/workflows/python-package.yml)
RTMA/Dragonfly client written in python with no external dependencies. Based on and compatible with [Dragonfly Messaging](https://github.com/pitt-rnel/rnel_dragonfly)

## Install
From root directory of the repo:
```shell
$ pip install .
```
## Usage
Launch MessageManager:
```shell
$ python manager.py -a "127.0.0.1"
```

Create a module:
```python
from pyrtma.client import Client

mod = Client()
mod.Connect('127.0.0.1:7111')
```

See /examples for pub/sub use case:

In one terminal run: 
```shell
$ python example.py --pub
```

And from another run: 
```shell
$ python example.py --sub
```

Bench testing utility: 
```shell
$ python testing/pyrtma_bench.py -h
usage: pyrtma_bench.py [-h] [-ms MSG_SIZE] [-n NUM_MSGS] [-np NUM_PUBLISHERS]
                     [-ns NUM_SUBSCRIBERS] [-s SERVER]

pyrtma Client bench test utility

optional arguments:
  -h, --help           show this help message and exit
  -ms MSG_SIZE         Messge size in bytes.
  -n NUM_MSGS          Number of messages.
  -np NUM_PUBLISHERS   Number of concurrent publishers.
  -ns NUM_SUBSCRIBERS  Number of concurrent subscribers.
  -s SERVER            RTMA message manager ip address (default:
                       127.0.0.1:7111)
```
