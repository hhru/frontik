#!/bin/sh
coverage run -p --branch --source=frontik -m tests
echo "\nWaiting for coverage to create files...\n" ; sleep 4
coverage combine ; coverage report -m
