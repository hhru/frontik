# --== Decompile ==--
import tornado.options
import logging
import logging.handlers
from logging import *
Filterer = logging.Filterer
if tornado.options.options.syslog:
	tornado.options.options.syslog
	_syslog_formatter = logging.Formatter('[%(asctime)s %(name)s] %(levelname)s %(message)s')
	_handler = logging.handlers.SysLogHandler(facility=logging.handlers.SysLogHandler.LOG_DEBUG, address=tornado.options.options.syslog_address)
	_handler.setFormatter(_syslog_formatter)
else:
	tornado.options.options.syslog
def getLogger(*args, **kwargs):
	log = logging.getLogger(*args, **kwargs)
	if tornado.options.options.syslog:
		tornado.options.options.syslog
		log.addHandler(_handler)
	else:
		tornado.options.options.syslog
	return log

