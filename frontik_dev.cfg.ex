host = '0.0.0.0'
port = 9300
workers_count = 1

daemonize = False

loglevel = 'debug'
logfile = None # log to stderr

pidfile = None

app_package = {
#    'app_name':  ('path/to/www', 'regexp', lambda regexp_match_obj, uri: return new uri ),

    'x':  ('path/to/x_www', '(/x)(/.*)', lambda match_obj, uri: match_obj.groups()[1] ),
    }

use_standart_doc = False

debug = True
debug_login = "hh"
debug_password = "12345"
