#!/bin/sh

DIR="`dirname $0`"

PYTHONPATH="$DIR" ./scripts/frontik_srv.py --config="$DIR/frontik_dev.cfg"
