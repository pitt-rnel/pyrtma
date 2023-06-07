from pyrtma.parser import Processor, Struct


class MatlabDefCompiler:
    def __init__(self, processor: Processor):
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
    
    def generate_fcn_close(self):
        return "end\n"
    
    def generate_field(self, top_field: str, name: str, value: str):
        name = name.replace(f"{top_field}_", "") # strip top_field from fieldname
        return f"{self.struct_name}.{top_field}.{name} = {value};\n"
    
    def generate_HID(self, name: str, value: str):
        return self.generate_field("HID", name, value)
    
    def generate_MID(self, name: str, value: str):
        return self.generate_field("MID", name, value)
    
    def generate_MT(self, name: str, value: str):
        return self.generate_field("MT", name, value)
    
    
    
    #def generate_vars(self):
    #    return f"{self.struct_name}.vars = [];\n"

    def generate(self, out_filepath: str):
        with open(out_filepath, mode="w") as f:
            
            # create RTMA config generator .m function
            f.write(self.generate_fcn_header(out_filepath.stem))
            
            # init struct
            f.write(self.initialize_struct())
            f.write("\n")
            
            # HID
            for name, expression in self.processor.HID.items():
                f.write(self.generate_HID(name, expression))
            f.write("\n")
            
            # MID
            for name, expression in self.processor.MID.items():
                f.write(self.generate_MID(name, expression))
            f.write("\n")
            
            # MT
            for name, expression in self.processor.MT.items():
                f.write(self.generate_MT(name, expression))
            f.write("\n")
            
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
            
