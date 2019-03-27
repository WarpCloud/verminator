#!/usr/bin/env bash

pip install -r tests/requirements.txt -i http://172.16.1.161:30033/repository/pypi/simple/ --trusted-host 172.16.1.161

nosetests --with-coverage --cover-package=verminator \
    --cover-erase --cover-tests --nocapture \
    -d --all-modules \
    tests