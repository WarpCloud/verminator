#!/bin/bash
rm -rf dist build
rm -rf verminator.egg-info
find . -name '*.pyc' -delete 
python setup.py sdist bdist_wheel bdist_egg
twine upload dist/*
