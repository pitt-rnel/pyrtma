from pyrtma.processor import Processor, Constant, TypeAlias, MT, MID, HID, MDF, SDF
from typing import Any, Union
from pathlib import Path
from textwrap import dedent

# Field type name to matlab types
type_map = {
    "char": "int8",
    "unsigned char": "uint8",
    "byte": "uint8",
    "int": "int32",
    "signed int": "int32",
    "unsigned int": "uint32",
    "unsigned": "uint32",
    "short": "int16",
    "signed short": "int16",
    "unsigned short": "uint16",
    "long": "int32",
    "signed long": "int32",
    "unsigned long": "uint32",
    "long long": "int64",
    "signed long long": "int64",
    "unsigned long long": "uint64",
    "float": "single",
    "double": "double",
    "MODULE_ID": "int16",
    "HOST_ID": "int16",
    "MSG_TYPE": "int32",
    "MSG_COUNT": "int32",
}


class MatlabDefCompiler:
    def __init__(self, processor: Processor, debug: bool = False):
        self.debug = debug
        self.processor = processor
        self.struct_name = "RTMA"

    def generate_fcn_header(self, fcn_name: str) -> str:
        return f"function {self.struct_name} = {fcn_name}()\n\n"
    
    def initialize_struct(self) -> str:
        mstruct = f"""
{self.struct_name} = struct('HID', [], 'MID', [], 'MT', [], 'MDF', [], 'MESSAGE_HEADER', [], ...
'MTN_by_MT', [], 'MDF_by_MT', [], 'mex_opcode', [], 'defines', [], 'typedefs', [], 'vars', []);
"""
        return mstruct
    
    @staticmethod
    def generate_fcn_close() -> str:
        return "end\n"
    
    @staticmethod
    def sanitize_name(name: str) -> str:
        name = name.lstrip('_0123456789') # strip leading characters that are invalid to start a fieldname (only letters allowed)
        for c in name:
            if not c.isalnum() and c != '_': # matlab fieldnames allow alphanum and _ after starting characters
                name = name.replace(c, '')
        return name
    
    def generate_field(self, top_field: str, name: str, value: Any) -> str:
        name = name.replace(f"{top_field}_", "", 1) # strip top_field from fieldname
        name = self.sanitize_name(name)
        return f"{self.struct_name}.{top_field}.{name} = {value};\n"
    
    def generate_constant(self, c: Union[Constant, HID, MID, MT]) -> str:
        if isinstance(c.value, str):
            c.value = f'"{c.value}"' # encase string value in quotes
        return self.generate_field("defines", c.name, c.value)
    
    def generate_host_id(self, hid: HID) -> str:
        return self.generate_field("HID", hid.name, hid.value)
    
    def generate_module_id(self, mid: MID) -> str:
        return self.generate_field("MID", mid.name, mid.value)
    
    def generate_msg_type_id(self, mt: MT) -> str:
        return self.generate_field("MT", mt.name, mt.value)
    
    def generate_type_alias(self, td: TypeAlias) -> str:
        ftype = type_map.get(td.type_name)
        if ftype:
            return self.generate_field("typedefs", td.name, f"{ftype}(0)")
        else:
            return self.generate_field("typedefs", td.name, f"{self.struct_name}.typedefs.{td.type_name}") # TODO validate this

    def generate_struct(self, sdf: Union[SDF, MDF], top_field: str = "typedefs") -> str:
        #assert not sdf.name.startswith("MDF_")
        f = []
        fnum = len(sdf.fields)
        fstr = ""
        if fnum == 0:
            fstr += f"{self.struct_name}.{top_field}.{sdf.name} = [];"
        else:
            for i, field in enumerate(sdf.fields, start=1):
                flen = field.length
                nl = "\n" #if i < fnum else ""
                ftype = type_map.get(field.type_name)

                if ftype is None:
                    stype = f"{self.struct_name}.typedefs.{field.type_name}" # does not work properly if flen > 1

                else:
                    stype = f"{ftype}(0)"

                if flen:
                    slen = f"({flen})"
                else:
                    slen = ""

                if flen:
                    f.append(
                        f"{self.struct_name}.{top_field}.{sdf.name}.{field.name} = repmat({stype}, 1, {flen});{nl}"
                    )
                else:
                    f.append(
                        f"{self.struct_name}.{top_field}.{sdf.name}.{field.name} = {stype};{nl}"
                    )

                fstr += "".join(f)

        return fstr

    def generate_msg_def(self, mdf: MDF) -> str:
        assert mdf.name.startswith("MDF_")
        mdf.name = mdf.name.replace(f"MDF_", "", 1) # strip top_field from fieldname
        return self.generate_struct(mdf, "MDF")
    
    def generate_message_header(self) -> str:
        return f"{self.struct_name}.MESSAGE_HEADER = {self.struct_name}.typedefs.RTMA_MSG_HEADER;\n"
    
    def generate_mex_opcodes(self) -> str:
        # these are copied from MatlabRTMA.h
        prefix = f"{self.struct_name}.mex_opcode"
        op = f"""\
        {prefix}.CONNECT_TO_MMM = 1;
        {prefix}.DISCONNECT_FROM_MMM = 2;
        {prefix}.SUBSCRIBE = 3;
        {prefix}.UNSUBSCRIBE = 4;
        {prefix}.SEND_MESSAGE = 5;
        {prefix}.SEND_SIGNAL = 6;
        {prefix}.READ_MESSAGE_HDR = 7;
        {prefix}.READ_MESSAGE_DATA = 8;
        {prefix}.SET_TIMER = 9;
        {prefix}.SEND_MODULE_READY = 10;
        {prefix}.CANCEL_TIMER = 11;
        {prefix}.PAUSE_SUBSCRIPTION = 12;
        {prefix}.RESUME_SUBSCRIPTION = 13;
        {prefix}.READ_MESSAGE_DD = 14;
        {prefix}.SEND_MESSAGE_DD = 15;
        {prefix}.GET_TIME = 16;
        {prefix}.GET_MODULE_ID = 17;
        """
        return dedent(op)
    
    def generate_vars(self):
        # do nothing (for now)
        return f"{self.struct_name}.vars = [];\n"

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
                    s = self.generate_struct(obj)
                    s += self.generate_msg_def(obj)
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

            # HID -- in loop
            
            # MID -- in loop
            
            # MT -- in loop
            
            # MDF -- in loop
            
            # MESSAGE_HEADER
            f.write(self.generate_message_header())
            
            # MTN_by_MT -- TODO
            
            # MDF_by_MT -- TODO
            
            # mex_opcode
            f.write(self.generate_mex_opcodes())
            
            # defines -- in loop
            
            # typedefs -- in loop
            
            # vars -- empty struct (for now)
            f.write(self.generate_vars())
            
            # close function
            f.write(self.generate_fcn_close())
        
