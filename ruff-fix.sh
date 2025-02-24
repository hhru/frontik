#!/bin/bash

ruff check --fix ./frontik ./tests
ruff format ./frontik ./tests
