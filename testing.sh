#!/usr/bin/env bash

nosetests --with-coverage --cover-package=verminator \
    --cover-erase --cover-tests --nocapture \
    -d --all-modules \
    tests