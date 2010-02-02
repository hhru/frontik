#coding: utf8

import os
import sys
import imp
import __builtin__
from functools import partial

def import_path(name, path=None, expose_name=None):
    f, filename, description = imp.find_module(name, [path])
    m = imp.load_module(expose_name or name, f, filename, description)
    f.close()
    return m
   
def import_hook(document_roots, name, globals=None, locals=None, fromlist=None):    
    if name.startswith("app.") and "%s/src" % os.path.commonprefix([os.path.dirname(globals["__file__"])] + document_roots.values()) in document_roots.values():
        dirname = os.path.dirname(globals["__file__"])
        app_name = "app__%s" % dict([(v, k) for k, v in document_roots.iteritems()])[os.path.join("/", *dirname.split("/")[:-2])]

        if sys.modules.has_key(name):
            return sys.modules[app_name]
        
        if sys.modules.has_key(app_name):
            parent = sys.modules[app_name]
        else:
            parent_path = os.path.abspath(os.path.join(dirname, "../"))
            parent = imp.load_source(app_name, "%s/__init__.py" % parent_path)
            parent.__path__ = parent_path
            sys.modules[app_name] = parent

        module_name = name.split(".")[-1:][0]
        f, filename, description = imp.find_module(module_name, [os.path.dirname(globals["__file__"]), parent.__path__])
        m = imp.load_module("%s.%s" % (app_name, module_name), f, filename, description)
        f.close()
        setattr(parent, module_name, m)
        sys.modules[name] = m
        return parent
    else:
        parent = determine_parent(globals)
        q, tail = find_head_package(parent, name)
        m = load_tail(q, tail)
        if not fromlist:
            return q
        if hasattr(m, "__path__"):
            ensure_fromlist(m, fromlist)
        return m

def determine_parent(globals):
    if not globals or  not globals.has_key("__name__"):
        return None
    pname = globals['__name__']
    if globals.has_key("__path__"):
        parent = sys.modules[pname]
        assert globals is parent.__dict__
        return parent
    if '.' in pname:
        i = pname.rfind('.')
        pname = pname[:i]
        parent = sys.modules[pname]
        assert parent.__name__ == pname
        return parent
    return None

def find_head_package(parent, name):
    if '.' in name:
        i = name.find('.')
        head = name[:i]
        tail = name[i+1:]
    else:
        head = name
        tail = ""

    if parent:
        qname = "%s.%s" % (parent.__name__, head)
    else:
        qname = head
    q = import_module(head, qname, parent)

    if q: 
        return q, tail

    if parent:
        qname = head
        parent = None
        q = import_module(head, qname, parent)

        if q:
            return q, tail
    raise ImportError, "No module named " + qname

def load_tail(q, tail):
    m = q
    while tail:
        i = tail.find('.')

        if i < 0:
            i = len(tail)
        head, tail = tail[:i], tail[i+1:]
        mname = "%s.%s" % (m.__name__, head)
        m = import_module(head, mname, m)

        if not m:
            raise ImportError, "No module named " + mname
    return m

def ensure_fromlist(m, fromlist, recursive=0):
    for sub in fromlist:
        if sub == "*":
            if not recursive:
                try:
                    all = m.__all__
                except AttributeError:
                    pass
                else:
                    ensure_fromlist(m, all, 1)
            continue
        if sub != "*" and not hasattr(m, sub):
            subname = "%s.%s" % (m.__name__, sub)
            submod = import_module(sub, subname, m)
            if not submod:
                raise ImportError, "No module named " + subname

def import_module(partname, fqname, parent):
    try:
        return sys.modules[fqname]
    except KeyError:
        pass
    try:
        fp, pathname, stuff = imp.find_module(partname, parent and parent.__path__)
    except ImportError:
        return None
    try:
        m = imp.load_module(fqname, fp, pathname, stuff)
    finally:
        if fp: 
            fp.close()
    if parent:
        setattr(parent, partname, m)
    return m

def reload_hook(module):
    name = module.__name__
    if '.' not in name:
        return import_module(name, name, None)
    i = name.rfind('.')
    pname = name[:i]
    parent = sys.modules[pname]
    return import_module(name[i+1:], name, parent)

def set_import_hooks(document_roots):
    original_import = __builtin__.__import__
    original_reload = __builtin__.reload

    __builtin__.__import__ = partial(import_hook, document_roots)
    __builtin__.reload = reload_hook

