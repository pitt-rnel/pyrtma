# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here.
import pathlib

# import sys
import os
from codecs import open

about = {}
here = pathlib.Path(__file__)  # os.path.abspath(os.path.dirname(__file__))
with open(
    (here.parents[2] / "src" / "pyrtma" / "__version__.py").resolve().as_posix(),
    "r",
    "utf-8",
) as f:
    exec(f.read(), about)

project = about["__title__"]
copyright = about["__copyright__"]
author = about["__author__"]
release = about["__version__"]

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.napoleon",  # support google and numpy style docstr
    "sphinx.ext.duration",  # build time
    "sphinx_rtd_theme",  # read the docs theme
    "myst_parser",  # support markdown myst
    "sphinx_copybutton",  # add copy button to code fields
    "sphinx.ext.autodoc",  # Core Sphinx library for auto html doc generation from docstrings
    "sphinx.ext.autosummary",  # Create neat summary tables for modules/classes/methods etc
    "sphinx_autodoc_typehints",  # Automatically document param types (less noise in class signature)
    "sphinx.ext.viewcode",  # Add a link to the Python source code for classes, functions etc.
    "sphinx.ext.intersphinx",  # Link to other project's documentation (see mapping below)
    #    'sphinx.ext.linkcode', # link to github code, disabled b/c I prefer viewcode
]

# Mappings for sphinx.ext.intersphinx. Projects have to have Sphinx-generated doc! (.inv file)
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
}

templates_path = ["_templates"]
exclude_patterns = []

# myst
myst_enable_extensions = ["colon_fence"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"  #'alabaster'
# html_static_path = ['_static']
# html_logo = ''

# EPUB options
epub_show_urls = "footnote"

# autodoc/autoapi
autodoc_typehints = "description"  # document types in description
autoclass_content = "both"  # Add __init__ doc (ie. params) to class summaries
set_type_checking_flag = True  # Enable 'expensive' imports for sphinx_autodoc_typehints
# autoapi_dirs = ['../../br_stimpy']
# autoapi_add_toctree_entry = False
# autoapi_template_dir = 'autoapi_templates'

# autosummary
autosummary_generate = True  # Turn on sphinx.ext.autosummary
autosummary_imported_members = True
add_module_names = False  # Remove namespaces from class/method signatures


# linkcode
def linkcode_resolve(domain, info):
    if domain != "py":
        return None
    if not info["module"]:
        return None
    filename = info["module"].replace(".", "/")
    return "https://github.com/pitt-rnel/pyrtma/blob/master/%s.py" % filename
