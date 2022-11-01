#!/usr/bin/env python3
import sys

if sys.version_info.major == 3 and sys.version_info.minor >= 10:
    import collections
    import collections.abc
    setattr(collections, "MutableMapping", collections.abc.MutableMapping)

from frontik.server import main

if __name__ == "__main__":
    main("./frontik.cfg")
