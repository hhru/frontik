# -*- coding: utf-8 -*-

def test():
    print 1

from urllib import urlencode

def list_unique(l):
    return list(set(l))

def _encode(s):
    if isinstance(s, unicode):
        return s.encode('utf-8')
    else:
        return s

def make_qs(query_args):
    kv_pairs = []
    for (key, val) in query_args.iteritems():
        if val:
            if isinstance(val, list):
                for v in val:
                    kv_pairs.append((key, _encode(v)))
            else:
                kv_pairs.append((key, _encode(val)))

    qs = urlencode(kv_pairs)

    return qs

def make_url(base, **query_args):
    ''' 
    построить URL из базового урла и набора CGI-параметров
    параметры с пустым значением пропускаются, удобно для последовательности:
    make_url(base, hhtoken=request.cookies.get('hhtoken'))
    '''
    qs = make_qs(query_args)

    if qs:
        return base + '?' + qs
    else:
        return base 

import os

def get_all_files(root, extension=None):
    out = list()
    for subdir, dirs, files in os.walk(root):
        out += [os.path.abspath(file) for file in files if extension and file.endswith(extension)]
    return out

from copy import copy

def dict_concat(dict1, dict2):
    """
    Returns content of dict1 after dict1.update(dict2)? without its modification
    """
    dict3 = copy(dict1)
    dict3.update(dict2)
    return dict3

import httplib
import mimetools, mimetypes

ENCODE_TEMPLATE= '--%(boundary)s\r\nContent-Disposition: form-data; name="%(name)s\r\n\r\n%(data)s\r\n'
ENCODE_TEMPLATE_FILE = '--%(boundary)s\r\nContent-Disposition: form-data; name="%(name)s"; filename="%(filename)s"\r\nContent-Type: %(contenttype)s\r\n\r\n%(data)s\r\n'

def get_content_type(filename):
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

def make_mfd(fields, files):
    ''' 
    Constructs request body in multipart/form-data format

    fields :: { field_name : field_value }
    files :: { field_name: [{ "filename" : fn, "body" : bytes }]}
    '''

    BOUNDARY = mimetools.choose_boundary()
    body = ""

    for name, data in fields.iteritems():

        if not data:
            continue

        if isinstance(data, list):
            for value in data:
                body += ENCODE_TEMPLATE % {
                            'boundary': BOUNDARY,
                            'name': str(name),
                            'data': _encode(value)
                        }
        else:
            body += ENCODE_TEMPLATE % {
                        'boundary': BOUNDARY,
                        'name': str(name),
                        'data': _encode(data)
                    }

    for name, files in files.iteritems():
        for file in files:
            body += ENCODE_TEMPLATE_FILE % {
                        'boundary': BOUNDARY,
                        'data': file["body"],
                        'name': name,
                        'filename': _encode(file["filename"]),
                        'contenttype': str(get_content_type(file["filename"]))
                    }

    body += '--%s\n\r' % BOUNDARY
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    return body, content_type
