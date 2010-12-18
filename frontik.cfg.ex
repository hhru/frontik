host = '0.0.0.0'
port = 8080
workers_count = 1

daemonize = True

loglevel = 'debug'
logfile = None # log to stderr

syslog = True
syslog_address = "/dev/log"

pidfile = None

apps = { 'page' : '/path/' }

use_standart_doc = False

debug = True
debug_login = "hh"
debug_password = "12345"
debug_xsl = "/usr/lib/frontik/debug.xsl"

