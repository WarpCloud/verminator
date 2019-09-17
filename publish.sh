#!/bin/bash
rm -rf dist build
python setup.py sdist bdist_wheel bdist_egg
twine upload dist/*
