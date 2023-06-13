from pyrtma.processor import Processor, Constant, TypeAlias, MT, MID, HID, MDF, SDF
from typing import Any
from pathlib import Path


class MatlabDefCompiler:
    def __init__(self, processor: Processor, debug: bool = False):
        self.debug = debug
        self.processor = processor
        self.struct_name = "RTMA"

    def generate_fcn_header(self, fcn_name: str):
        return f"function {self.struct_name} = {fcn_name}()\n\n"
    
    def initialize_struct(self):
        mstruct = f"""
{self.struct_name} = struct('HID', [], 'MID', [], 'MT', [], 'MDF', [], 'MESSAGE_HEADER', [], ...
'MTN_by_MT', [], 'MDF_by_MT', [], 'mex_opcode', [], 'defines', [], 'typedefs', [], 'vars', []);
"""
        return mstruct
    
    @staticmethod
    def generate_fcn_close():
        return "end\n"
    
    @staticmethod
    def sanitize_name(name: str) -> str:
        name = name.lstrip('_0123456789') # strip leading characters that are invalid to start a fieldname
        for c in name:
            if not c.isalpha() and c != '_':
                name = name.replace(c, '')
        return name
    
    def generate_field(self, top_field: str, name: str, value: Any):
        name = name.replace(f"{top_field}_", "") # strip top_field from fieldname
        name = self.sanitize_name(name)
        return f"{self.struct_name}.{top_field}.{name} = {value};\n"
    
    def generate_constant(self, c: Constant):
        if isinstance(c.value, str):
            c.value = f'"{c.value}"' # encase string value in quotes
        return self.generate_field("defines", c.name, c.value)
    
    def generate_host_id(self, hid: HID):
        return self.generate_field("HID", hid.name, hid.value)
    
    def generate_module_id(self, mid: MID):
        return self.generate_field("MID", mid.name, mid.value)
    
    def generate_msg_type_id(self, mt: MT):
        return self.generate_field("MT", mt.name, mt.value)
    
    def generate_type_alias(self, td: TypeAlias):
        return ""

    def generate_struct(self, sdf: SDF):
        return ""

    def generate_msg_def(self, mdf: MDF):
        return ""
    
    #def generate_vars(self):
    #    return f"{self.struct_name}.vars = [];\n"

    def generate(self, out_filepath: Path):

        if self.debug:
            print(out_filepath)

        with open(out_filepath, mode="w") as f:
            
            # create RTMA config generator .m function
            f.write(self.generate_fcn_header(out_filepath.stem))
            
            # init struct
            f.write(self.initialize_struct())
            f.write("\n")
            
            prev_obj = None
            for obj in self.processor.objs:
                s = ""
                if type(obj) is Constant:
                    s = self.generate_constant(obj)
                elif type(obj) is MT:
                    s = self.generate_constant(obj)
                    s += self.generate_msg_type_id(obj)
                elif type(obj) is MID:
                    s = self.generate_constant(obj)
                    s += self.generate_module_id(obj)
                elif type(obj) is HID:
                    s = self.generate_constant(obj)
                    s += self.generate_host_id(obj)
                elif type(obj) is MDF:
                    s = self.generate_msg_def(obj)
                elif type(obj) is SDF:
                    s = self.generate_struct(obj)
                elif type(obj) is TypeAlias:
                    s = self.generate_type_alias(obj)
                else:
                    raise RuntimeError(f"Unknown rtma object type of {type(obj)}")
                
                # Add two lines before struct definition after a define
                if type(prev_obj) in (Constant, MT, MID, HID):
                    if type(obj) in (TypeAlias, MDF, SDF):
                        f.write("\n\n")

                # Write the generated code
                f.write(s)

                # Add two lines after a struct definition
                if type(obj) in (TypeAlias, MDF, SDF):
                    f.write("\n\n")

                # Store the previous object generated
                prev_obj = obj

                if self.debug:
                    print(s, end="")

            # HID
            
            # MID
            
            # MT
            
            # MDF
            
            # MESSAGE_HEADER
            
            # MTN_by_MT
            
            # MDF_by_MT
            
            # mex_opcode
            
            # defines
            
            # typedefs
            
            # vars
            #f.write(self.generate_vars())
            
            
            # close function
            f.write(self.generate_fcn_close())
        breakpoint()
            
