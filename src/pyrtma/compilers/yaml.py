import pathlib
import sys
from pyrtma.parser import Parser
from ruamel.yaml import YAML


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
        yaml.dump(self.parser.yaml_dict, out_filepath)
