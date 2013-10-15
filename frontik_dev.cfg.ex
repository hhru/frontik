from frontik.app import App

host = '0.0.0.0'
port = 9300
workers_count = 1

daemonize = False

loglevel = 'debug'
logfile = None  # log to stderr

pidfile = None

urls = [
    #format:    (regexp, dispatcher),
    ("/page", App("hh-xhh", "/usr/share/pyshared/xhh"))
]
# where dispatcher is an App or any other dispatcher, like frontik.app.RegexDispatcher for example

debug = True
debug_login = "hh"
debug_password = "12345"

# wait this number of seconds (int) in workers before stopping IOLoop in each worker,
# should be a little less than supervisor_sigterm_timeout
stop_timeout = 4

# wait this number of seconds (int) in supervisor after sending SIGTERM to all workers and wait
# 0.1*workers_count seconds more after sending SIGKILL
supervisor_sigterm_timeout = 5

# call long request handler if page did not finish after this amount of seconds
# remove or set to None to disable timeouts
long_request_timeout = None

# kill requests that did not finish after long_request_timeout
kill_long_requests = False

log_blocked_ioloop_timeout = 2.0
