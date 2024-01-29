import pathlib
import sys
from pyrtma.parser import Parser
from ruamel.yaml import YAML
from typing import Dict, Any, Optional, Union
from pyrtma.__version__ import __version__


class NullRepresenter:
    def __init__(self):
        self.count = 0

    def __call__(self, repr, data):
        return repr.represent_scalar("tag:yaml.org,2002:null", "null")


class YAMLCompiler:
    def __init__(self, parser: Parser, filename: str, debug: bool = False):
        self.filename = filename
        self.debug = debug
        self.parser = parser

    def generate(self, out_filepath: pathlib.Path):
        yaml = YAML()
        yaml.default_flow_style = False
        my_represent_none = NullRepresenter()
        yaml.representer.add_representer(type(None), my_represent_none)

        meta_dict: Dict[str, Any] = {
            "COMPILED_PYRTMA_VERSION": __version__,
            "AUTOGENERATED": True,
        }
        options_dict: Dict[str, Any] = {"IMPORT_COREDEFS": False}

        d: Dict[str, Optional[Dict[str, Any]]] = {
            "metadata": {},
            "compiler_options": {},
        }

        for k, v in self.parser.yaml_dict.items():
            if isinstance(v, dict) and len(v) == 0:
                d[k] = None
            else:
                d[k] = v
        for k, v in meta_dict.items():
            if d["metadata"] is None:
                d["metadata"] = {}
            if isinstance(d["metadata"], dict) and isinstance(v, dict) and len(v) == 0:
                d["metadata"][k] = None
            elif isinstance(d["metadata"], dict):
                d["metadata"][k] = v
        for k, v in options_dict.items():
            if d["compiler_options"] is None:
                d["compiler_options"] = {}
            if (
                isinstance(d["compiler_options"], dict)
                and isinstance(v, dict)
                and len(v) == 0
            ):
                d["compiler_options"][k] = None
            elif isinstance(d["compiler_options"], dict):
                d["compiler_options"][k] = v

        yaml.dump(d, out_filepath)
