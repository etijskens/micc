#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for C++ module {{ cookiecutter.project_name }}.{{ cookiecutter.module_name }}.
"""

import os
import sys
import pytest
#===============================================================================
# Make sure that the current directory is the project directory.
# 'make test" and 'pytest' are generally run from the project directory.
# However, if we run/debug this file in eclipse, we end up in test
if os.getcwd().endswith('tests'):
    print(f"Changing current working directory"
          f"\n  from '{os.getcwd()}'"
          f"\n  to   '{os.path.abspath(os.path.join(os.getcwd(),'..'))}'.\n")
    os.chdir('..')
#===============================================================================
# Make sure that we can import the module being tested. When running
# 'make test" and 'pytest' in the project directory, the current working
# directory is not automatically added to sys.path.
if not ('.' in sys.path or os.getcwd() in sys.path):
    print(f"Adding '.' to sys.path.\n")
    sys.path.insert(0, '.')
#===============================================================================
import {{ cookiecutter.package_name }}.{{ cookiecutter.module_name }} as cpp
#===============================================================================
def test_cpp_function():
    """
    Test a C++ function.
    """
    i,j=2,3
    expected = i + j
    result = cpp.add(i,j)
    assert result == expected
#===============================================================================
# The code below is for debugging a particular test in eclipse/pydev.
# (normally all tests are run with pytest)
#===============================================================================
if __name__ == "__main__":
    the_test_you_want_to_debug = test_cpp_function

    print(f"__main__ running {the_test_you_want_to_debug} ...")
    the_test_you_want_to_debug()
    print('-*# finished #*-')
#===============================================================================
