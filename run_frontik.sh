#!/bin/sh

PROG="${0##*/}"
DIR="$(dirname $(readlink -f $0))"

show_help()
{
        cat <<EOF
Usage: $PROG [options] [-- [frontik options]]

$PROG start frontik from Git checkout

Options:
  --config=<config_file>  config file
  -h,--help               show this text and exit.

EOF
        exit
}

fatal() {
        message "$@"
        exit 1
}

CONFIG="$DIR/frontik_dev.cfg"

TEMP=`getopt -n $PROG -o h\
             -l config:,help, -- "$@"` ||
        show_help

eval set -- "$TEMP"

while :; do
    case "$1" in
        --config)
            shift;
            CONFIG="$1"
            ;;
        -h|--help)
	    show_help
	    ;;
        --)
	    shift;
	    break
	    ;;
        *)
	    fatal "unrecognized option: $1";;
    esac
    shift
done

export PYTHONPATH="$DIR:$PYTHONPATH"
python $DIR/scripts/frontik --config="$CONFIG" "$@"
