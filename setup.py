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
# https://packaging.python.org/en/latest/distributing/#working-in-development-mode
# http://python-packaging-user-guide.readthedocs.org/en/latest/distributing/
# http://jtushman.github.io/blog/2013/06/17/sharing-code-across-applications-with-python/  # noqa

from setuptools import setup
from codecs import open
from os import path

from whisker_serial_order.version import VERSION

here = path.abspath(path.dirname(__file__))

# -----------------------------------------------------------------------------
# Get the long description from the README file
# -----------------------------------------------------------------------------
with open(path.join(here, 'README.txt'), encoding='utf-8') as f:
    long_description = f.read()

# -----------------------------------------------------------------------------
# setup args
# -----------------------------------------------------------------------------
setup(
    name='whisker_serial_order',

    version=VERSION,

    description='Serial order task for Whisker',
    long_description=long_description,

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
        'Programming Language :: Python :: 3 :: Only',

        'Topic :: System :: Hardware',
        'Topic :: System :: Networking',
    ],

    keywords='whisker research control',

    packages=['whisker_serial_order'],

    install_requires=[
        'arrow',  # better datetime
        'mysqlclient',  # MySQL engine (Python 3 replacement for MySQLdb)
        # 'psycopg2',  # PostgreSQL engine; but requires PostgreSQL installed
        # ... (fails with error re missing pg_config otherwise)
        'PySide==1.2.4',  # Python interface to Qt
        'SQLAlchemy',  # SQL Alchemy database interface
        'sqlalchemy-utils',  # http://sqlalchemy-utils.readthedocs.org/
        'sadisplay',  # SQL Alchemy schema display script
        'whisker>=0.2.0',  # Whisker client library

        # ---------------------------------------------------------------------
        # For development only:
        # ---------------------------------------------------------------------
        # docutils  # includes rst2html.py
        # twine  # for uploading to PyPI
    ],

    entry_points={
        'console_scripts': [
            # Format is 'script=module:function".
            'whisker_serial_order=whisker_serial_order.main:main',
        ],
    },
)
