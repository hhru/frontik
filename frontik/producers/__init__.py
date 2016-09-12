# coding=utf-8


class ProducerFactory(object):
    def get_producer(self, handler):
        raise NotImplementedError()
