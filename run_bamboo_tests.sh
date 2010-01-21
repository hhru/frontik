#!/bin/sh

# каталог /home/bamboo/python-bamboo-libs/ наполняется командой
# PYTHONPATH=/home/bamboo/python-bamboo-libs/ easy_install -d /home/bamboo/python-bamboo-libs/ -U NoseXUnit

rm -rf tmp
mkdir -p tmp
cd tmp

git clone http://github.com/elephantum/tornado.git
git clone http://github.com/elephantum/tornado-util.git
git clone http://github.com/elephantum/python-daemon.git

cd ../src
export PYTHONPATH=/home/bamboo/python-bamboo-libs/:tmp/tornado:tmp/tornado-util:tmp/python-daemon:test 

/home/bamboo/python-bamboo-libs/nosetests --with-nosexunit