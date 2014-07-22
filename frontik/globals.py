import time

import frontik.producers.json_producer
import frontik.producers.xml_producer

import tornado.curl_httpclient


class ApplicationGlobals(object):
    """ Global settings for Frontik instance """
    def __init__(self, app_package):
        self.config = app_package.config

        self.xml = frontik.producers.xml_producer.ApplicationXMLGlobals(app_package.config)
        self.json = frontik.producers.json_producer.ApplicationJsonGlobals(app_package.config)

        self.http_client = tornado.curl_httpclient.CurlAsyncHTTPClient(max_clients=200)


class Stats(object):
    def __init__(self):
        self.page_count = 0
        self.http_reqs_count = 0
        self.http_reqs_size_sum = 0
        self.start_time = time.time()

    def next_request_id(self):
        self.page_count += 1
        return self.page_count

global_stats = Stats()
