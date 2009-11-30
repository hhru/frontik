#!/bin/sh

case "$1" in
  start)
	/usr/bin/frontik_supervisor.py --start
        ;;
  stop)
	/usr/bin/frontik_supervisor.py --stop
        ;;
  restart|force-reload)
	/usr/bin/frontik_supervisor.py --stop
	/usr/bin/frontik_supervisor.py --start
	;;
  *)
        N=/etc/init.d/frontik
        echo "Usage: $N {start|stop|force-stop|restart|force-reload|status}" >&2
        exit 1
        ;;
esac

exit 0
