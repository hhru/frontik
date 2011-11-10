#!/bin/sh

version=`dpkg-parsechangelog| grep Version | sed "s/^Version: \(.*\)/\1/"`
echo "version = '$version'" > debian/frontik/usr/share/pyshared/frontik/version.py
