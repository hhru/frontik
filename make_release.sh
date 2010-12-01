#!/bin/sh -e

PROG="${0##*/}"

show_help()
{
        cat <<EOF
Usage: $PROG [options]

$PROG properly makes releases

Options:
  --update-major      after release update major version component
  --update-minor      after release update minor version component
  --update-subminor   after release update subminor version component

  -h,--help           show this text and exit.

EOF
        exit
}

fatal() {
        message "$@"
        exit 1
}

update="minor"


TEMP=`getopt -n $PROG -o h,m,s\
             -l help,update-major,update-minor,update-subminor -- "$@"` ||
        show_help

eval set -- "$TEMP"

while :; do
    case "$1" in
        --update-major)
	    update="major"
	    ;;
        --update-minor)
	    update="minor"
	    ;;
        --update-subminor)
	    update="subminor"
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

eval `python -c 'print "VERSION_MAJOR={0} VERSION_MINOR={1} VERSION_SUBMINOR={2} VERSION_TYPE={3}".format(*__import__("frontik").VERSION)'`

[ "x$VERSION_TYPE" != "xdev" ] && fatal "VERSION_TYPE must be \"dev\", not \"$VERSION_TYPE\"!"

VERSION_TYPE="final"
DOTTED_VERSION="$VERSION_MAJOR.$VERSION_MINOR.$VERSION_SUBMINOR"

sed -i "s/^VERSION = .*$/VERSION = ($VERSION_MAJOR, $VERSION_MINOR, $VERSION_SUBMINOR, \"$VERSION_TYPE\")/" frontik/__init__.py

dch -D unstable --force-distribution -v "$DOTTED_VERSION" -- "frontik $DOTTED_VERSION"
dch -e

git commit -m "frontik $DOTTED_VERSION" debian/changelog frontik/__init__.py
git tag -a -m "frontik $DOTTED_VERSION" "v$DOTTED_VERSION"

VERSION_TYPE="dev"
case "$update" in
    major)
	VERSION_MAJOR=$((VERSION_MAJOR+1))
	VERSION_MINOR=0
	VERSION_SUBMINOR=0
	;;
    minor)
	VERSION_MINOR=$((VERSION_MINOR+1))
	VERSION_SUBMINOR=0
	;;
    subminor)
	VERSION_SUBMINOR=$((VERSION_SUBMINOR+1))
	;;
esac

DOTTED_VERSION="$VERSION_MAJOR.$VERSION_MINOR.$VERSION_SUBMINOR"

dch -D UNRELEASED -v "$DOTTED_VERSION~dev" -- "New development version"
sed -i "s/^VERSION = .*$/VERSION = ($VERSION_MAJOR, $VERSION_MINOR, $VERSION_SUBMINOR, \"$VERSION_TYPE\")/" frontik/__init__.py
