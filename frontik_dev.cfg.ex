from frontik.app import App

host = '0.0.0.0'
port = 9300
workers_count = 1

daemonize = False

loglevel = 'debug'
logfile = None # log to stderr

pidfile = None

urls = [
#format:    (regexp,                    dispatcher),
            (r".*",                     App("app_name", "/path/to/app/www_root") ),
            (r"/echo/(?P<id>(\d+))?",   SomeHandler),
]
# where dispatcher is an App or any other dispatcher, like frontik.app.RegexDispatcher for example

use_standart_doc = False

debug = True
debug_login = "hh"
debug_password = "12345"
