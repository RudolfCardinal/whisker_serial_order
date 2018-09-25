#!/usr/bin/env python
# setup.py

"""
whisker_serial_order setup file

To use:

    python setup.py sdist

    twine upload dist/*

To install in development mode:

    pip install -e .

"""
# https://packaging.python.org/en/latest/distributing/#working-in-development-mode  # noqa
# http://python-packaging-user-guide.readthedocs.org/en/latest/distributing/
# http://jtushman.github.io/blog/2013/06/17/sharing-code-across-applications-with-python/  # noqa

import argparse
from setuptools import setup
from codecs import open
import fnmatch
import os
from pprint import pformat
import sys
from typing import List

from whisker_serial_order.version import SERIAL_ORDER_VERSION


# =============================================================================
# Helper functions
# =============================================================================

# Files not to bundle
SKIP_PATTERNS = ['*.pyc', '~*']


def add_all_files(root_dir: str,
                  filelist: List[str],
                  absolute: bool = False,
                  include_n_parents: int = 0,
                  verbose: bool = True,
                  skip_patterns: List[str] = None) -> None:
    skip_patterns = skip_patterns or SKIP_PATTERNS
    if absolute:
        base_dir = root_dir
    else:
        base_dir = os.path.abspath(
            os.path.join(root_dir, *(['..'] * include_n_parents)))
    for dir_, subdirs, files in os.walk(root_dir, topdown=True):
        if absolute:
            final_dir = dir_
        else:
            final_dir = os.path.relpath(dir_, base_dir)
        for filename in files:
            _, ext = os.path.splitext(filename)
            final_filename = os.path.join(final_dir, filename)
            if any(fnmatch.fnmatch(final_filename, pattern)
                   for pattern in skip_patterns):
                if verbose:
                    print("Skipping: {}".format(final_filename))
                continue
            if verbose:
                print("Adding: {}".format(final_filename))
            filelist.append(final_filename)


# =============================================================================
# Constants
# =============================================================================

# Arguments
EXTRAS_ARG = 'extras'

# Directories
THIS_DIR = os.path.abspath(os.path.dirname(__file__))  # .../whisker_serial_order  # noqa

# Files
MANIFEST_FILE = os.path.join(THIS_DIR, 'MANIFEST.in')  # we will write this
PIP_REQ_FILE = os.path.join(THIS_DIR, 'requirements.txt')

# Get the long description from the README file
with open(os.path.join(THIS_DIR, 'README.txt'), encoding='utf-8') as f:
    LONG_DESCRIPTION = f.read()

# Package dependencies
INSTALL_REQUIRES = [
    'alembic==1.0.0',  # migration tool for sqlalchemy
    'arrow==0.10.0',  # better datetime
    'attrdict==2.0.0',
    'cardinal_pythonlib==1.0.28',
    'python-dateutil==2.7.3',
    'PyQt5==5.8',  # Python interface to Qt
    'SQLAlchemy==1.2.12',  # SQL Alchemy database interface
    'sqlalchemy-utils==0.32.5',  # http://sqlalchemy-utils.readthedocs.org/
    'sadisplay==0.4.9',  # SQL Alchemy schema display script
    'whisker==1.1.0',  # Whisker client library

    # 'mysqlclient',  # MySQL engine (Python 3 replacement for MySQLdb)
    #       ... but under Windows, a right pain to install; use
    #       https://dev.mysql.com/downloads/connector/python/ instead
    # 'psycopg2',  # PostgreSQL engine; but requires PostgreSQL installed
    #       ... (fails with error re missing pg_config otherwise)

    # ---------------------------------------------------------------------
    # For development only:
    # ---------------------------------------------------------------------
    # pyinstaller==3.4  # for building packaged executables
    # twine  # for uploading to PyPI
    # sphinx  # for building docs
]


# =============================================================================
# If we run this with "python setup.py sdist --extras", we *BUILD* the package
# and do all the extras. (When the end user installs it, that argument will be
# absent.)
# =============================================================================

parser = argparse.ArgumentParser()
parser.add_argument(
    '--' + EXTRAS_ARG, action='store_true',
    help=(
        "USE THIS TO CREATE PACKAGES (e.g. 'python setup.py sdist --{}. "
        "Copies extra info in.".format(EXTRAS_ARG)
    )
)
our_args, leftover_args = parser.parse_known_args()
sys.argv[1:] = leftover_args

extra_files = []  # type: List[str]

if getattr(our_args, EXTRAS_ARG):
    # Here's where we do the extra stuff.

    # Write the manifest.
    extra_files.sort()
    print("EXTRA_FILES: \n{}".format(pformat(extra_files)))
    manifest_lines = ['include ' + x for x in extra_files]

    # manifest_lines.append("recursive-exclude *.pyc")
    # ... because (2019-09-09) we had a problem with a __pycache__ directory
    #     for some reason appearing in
    #     "whisker_serial_order.egg-info/SOURCES.txt".
    # ... no; was a non-problem; ignore that.

    with open(MANIFEST_FILE, 'wt') as manifest:
        manifest.writelines([
            "# This is an AUTOCREATED file, MANIFEST.in; see setup.py and DO "
            "NOT EDIT BY HAND"])
        manifest.write("\n\n" + "\n".join(manifest_lines) + "\n")

    # Does autowriting requirements.txt help PyCharm?
    with open(PIP_REQ_FILE, "w") as req_file:
        for line in INSTALL_REQUIRES:
            req_file.write(line + "\n")


# =============================================================================
# setup args
# =============================================================================

setup(
    name='whisker_serial_order',

    version=SERIAL_ORDER_VERSION,

    description='Serial order task for Whisker',
    long_description=LONG_DESCRIPTION,

    # The project's main homepage.
    url='http://www.whiskercontrol.com/',

    # Author details
    author='Rudolf Cardinal',
    author_email='rudolf@pobox.com',

    # Choose your license
    license='Apache License 2.0',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Science/Research',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: Apache Software License',

        'Natural Language :: English',

        'Operating System :: OS Independent',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3 :: Only',

        'Topic :: System :: Hardware',
        'Topic :: System :: Networking',
    ],

    keywords='whisker research control',

    packages=['whisker_serial_order'],
    # packages=find_packages(),  # finds all the .py files in subdirectories

    package_data={
        'whisker_serial_order': [
            'alembic.ini',
            'alembic/env.py',
            'alembic/script.py.mako',
            'alembic/versions/*.py',
        ],
    },

    include_package_data=True,  # use MANIFEST.in during install?

    install_requires=INSTALL_REQUIRES,

    entry_points={
        'console_scripts': [
            # Format is 'script=module:function".
            'whisker_serial_order=whisker_serial_order.main:main',
        ],
    },
)
