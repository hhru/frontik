FROM registry.pyn.ru:5000/python3.7-ubuntu18-production:2019.04.10

COPY frontik-test setup.py README.md MANIFEST.in /home/building/
COPY frontik /home/building/frontik/
COPY tests /home/building/tests/
COPY examples /home/building/examples/
COPY scripts /home/building/scripts/
WORKDIR /home/building

RUN pip3 install raven
RUN python3.7 setup.py install
RUN python3.7 setup.py test
