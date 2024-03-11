__title__ = "pyrtma"
__description__ = "A Python compiler and client for RTMA/Dragonfly messaging system"
__url__ = "https://github.com/pitt-rnel/pyrtma"
__version__ = "2.2.2"
__author__ = "RNEL"
__author_email__ = ""
__license__ = "MIT"
__copyright__ = "University of Pittsburgh Rehab Neural Engineering Labs, 2024"


def check_compiled_version(compiled_version: str):
    from packaging.version import parse as ver_parse
    from warnings import warn
    from .exceptions import VersionMismatchWarning

    if ver_parse(__version__) < ver_parse(compiled_version):
        warn(
            f"Message defs compiled with pyrtma=={compiled_version} are newer than installed version pyrtma=={__version__}.\nPlease update pyrtma with `pip install pyrtma --upgrade`",
            VersionMismatchWarning,
            stacklevel=2,
        )
    elif ver_parse(compiled_version) < ver_parse(__version__):
        warn(
            f"Message defs compiled with pyrtma=={compiled_version} are older than installed version pyrtma=={__version__}.\nPlease update message defs.",
            VersionMismatchWarning,
            stacklevel=2,
        )
