#!/bin/sh
coverage run setup.py test --with-coverage
echo "\nWaiting for coverage to create files...\n" ; sleep 5
coverage combine ; coverage report -m
