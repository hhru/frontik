# -*- coding: utf-8 -*-

import urllib

def make_url(base, **query_args):
    ''' 
    построить URL из базового урла и набора CGI-параметров
    параметры с пустым значением пропускаются, удобно для последовательности:
    make_url(base, hhtoken=request.cookies.get('hhtoken'))
    '''
    
    kv_pairs = []
    for (key, val) in query_args.iteritems():
        if val:
            if isinstance(val, list):
                for v in val:
                    kv_pairs.append((key, v))
            else:
                kv_pairs.append((key, val))
    
    qs = urllib.urlencode(kv_pairs)
    
    if qs:
        return base + '?' + qs
    else:
        return base 

