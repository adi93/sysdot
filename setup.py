#!/usr/bin/env python3
#
# The purpose of this script is to enable uploading sysdot.py to the Python
# Package Index, which can be easily done by doing:
#
#   python3 setup.py sdist upload
#
# See also:
# - https://packaging.python.org/distributing/
# - https://docs.python.org/3/distutils/packageindex.html
#

from setuptools import setup

setup(
    name='sysdot',
    version='1.1',
    author='Aditya Harit',
    author_email='adityah@uci.edu',
    description="Interactive viewer for (RISC) Graphviz dot files",
    long_description="""
        sysdot.py is a modification of the xdot tool written by Jose Fonseca.

        It is tailored towards visualizing conflict graphs for RISC compiler.
        """,
    license="LGPL",

    packages=['sysdot', 'sysdot/dot', 'sysdot/ui', 'sysdot/conflict'],
    entry_points=dict(gui_scripts=['sysdot=sysdot.__main__:main']),

    # https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 6 - Mature',

        'Environment :: X11 Applications :: GTK',

        'Intended Audience :: Information Technology',

        'Operating System :: OS Independent',

        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3 :: Only',

        'Topic :: Multimedia :: Graphics :: Viewers',
    ],

    # This is true, but doesn't work realiably
    #install_requires=['gi', 'gi-cairo'],
)
