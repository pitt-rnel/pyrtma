import re


def camelcase(name):
    name = re.sub(r"_", " ", name)
    pieces = [s.title() for s in name.split(sep=" ")]
    return "".join(pieces)


# Field type name to ctypes
supported_types = [
    "char",
    "unsigned char",
    "byte",
    "int",
    "signed int",
    "unsigned int",
    "unsigned",
    "short",
    "signed short",
    "unsigned short",
    "long",
    "signed long",
    "unsigned long",
    "long long",
    "signed long long",
    "unsigned long long",
    "float",
    "double",
    "int8_t",
    "int16_t",
    "int32_t",
    "int64_t",
    "uint8_t",
    "uint16_t",
    "uint32_t",
    "uint64_t",
    "MODULE_ID",
    "HOST_ID",
    "MSG_TYPE",
    "MSG_COUNT",
]


class Parser:
    def __init__(self):
        self.constants = {}
        self.MT = {}
        self.MID = {}
        self.typedefs = {}
        self.structs = {}

        self.files = []

    def preprocess(self, text: str) -> str:
        # Strip Inline Comments
        text = re.sub(r"//(.*)\n", r"\n", text)

        # Strip Block Comments
        text = re.sub(r"/\*(.*?)\*/", r"\n", text, flags=re.DOTALL)

        # Strip Tabs
        text = re.sub(r"\t+", " ", text)

        return text

    def parse_defines(self, text: str):
        # Get Defines (Only simple one line constants here)
        macros = re.findall(
            r"#define\s*(?P<name>\w+)\s+(?P<expression>[\(\)\[\]\w \*/\+-\.]+)\n", text
        )

        for name, exp in macros:
            name = name.strip()
            exp = exp.strip()

            # Store a mapping for each define type
            if name.startswith("MT_"):
                if self.MT.get(name) is None:
                    self.MT[name] = exp
                else:
                    raise KeyError(f"Duplicate MT definition found: {name}")
            elif name.startswith("MID_"):
                if self.MID.get(name) is None:
                    self.MID[name] = exp
                else:
                    raise KeyError(f"Duplicate MID definition found: {name}")
            else:
                if self.constants.get(name) is None:
                    self.constants[name] = exp
                else:
                    raise KeyError(f"Duplicate constant definition found: {name}")

            # Organize in ascending order
            self.MT = {
                k: v for k, v in sorted(list(self.MT.items()), key=lambda x: x[1])
            }
            self.MID = {
                k: v for k, v in sorted(list(self.MID.items()), key=lambda x: x[1])
            }

    def parse_typedefs(self, text: str):
        # Get simple typedefs
        c_typedefs = re.finditer(
            r"\s*typedef\s+(?P<qual1>\w+\s+)?\s*(?P<qual2>\w+\s+)?\s*(?P<typ>\w+)\s+(?P<name>\w+)\s*;\s*$",
            text,
            flags=re.MULTILINE,
        )

        for m in c_typedefs:
            alias = m.group("name").strip()
            if alias.startswith("MDF_"):
                # TODO:Non struct message defintion. Maybe drop support?
                pass
            else:
                # Field type
                qual1 = m.group("qual1")
                qual2 = m.group("qual2")
                typ = m.group("typ")

                ftype = ""
                if qual1:
                    ftype += qual1.strip()
                    ftype += " "

                if qual2:
                    ftype += qual2.strip()
                    ftype += " "

                ftype += typ.strip()

                # Must be a native type
                assert ftype in supported_types, f"{ftype} is not supported."

                # Create another alias for the native type
                self.typedefs[alias.strip()] = ftype

    def parse_structs(self, text: str):
        # Strip Newlines
        text = re.sub(r"\n", "", text)
        # Get Struct Definitions
        c_msg_defs = re.finditer(
            r"\s*typedef\s+struct\s*\{(?P<def>.*?)\}(?P<name>\s*\w*)\s*;", text
        )

        for m in c_msg_defs:
            name = m.group("name").strip()
            fields = m.group("def").split(sep=";")
            fields = [f.strip() for f in fields if f.strip() != ""]
            c_fields = []

            for field in fields:
                fmatch = re.match(
                    r"(?P<qual1>\w+\s+)?\s*(?P<qual2>\w+\s+)?\s*(?P<typ>\w+)\s+(?P<name>\w+)\s*(\[(?P<length>.*)\])?$",
                    field,
                )

                if fmatch is None:
                    print(field)
                    raise RuntimeError("Error parsing field definition.")

                # Field name
                fname = fmatch.group("name").strip()
                qual1 = fmatch.group("qual1")
                qual2 = fmatch.group("qual2")
                typ = fmatch.group("typ")

                ftype = ""
                if qual1:
                    ftype += qual1.strip()
                    ftype += " "

                if qual2:
                    ftype += qual2.strip()
                    ftype += " "

                ftype += typ.strip()

                flen = fmatch.group("length") or None
                c_fields.append((fname, ftype, flen))

            self.structs[name] = tuple(c_fields)

        # Add a placeholder for signal definitions
        for msg_type in self.MT.keys():
            if msg_type.startswith("MT_"):
                self.structs.setdefault("MDF_" + msg_type[3:], None)

    def parse_file(self, filename):
        """Parse a C header file for message definitions.
        Notes:
            * Does not follow other #includes
            * Parsing order: #defines, typedefs, typedef struct
        """

        self.files.append(filename)

        with open(filename, "r") as f:
            raw = f.read()

        text = self.preprocess(raw)
        self.parse_defines(text)
        self.parse_typedefs(text)
        self.parse_structs(text)

    def parse(self, files):
        for file in files:
            self.parse_file(file)
