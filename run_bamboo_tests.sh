#!/bin/sh

# каталог /home/bamboo/python-bamboo-libs/ наполняется командой
# PYTHONPATH=/home/bamboo/python-bamboo-libs/ easy_install -d /home/bamboo/python-bamboo-libs/ -U NoseXUnit

cd src
PYTHONPATH=/home/bamboo/python-bamboo-libs/:test /home/bamboo/python-bamboo-libs/nosetests --with-nosexunit