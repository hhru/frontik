# -*- coding: utf-8 -*-

import urllib

from hh.http_client import http_get

import config

def make_url(base, **query_args):
    ''' 
    построить URL из базового урла и набора CGI-параметров
    параметры с пустым значением пропускаются, удобно для последовательности:
    make_url(base, hhtoken=request.cookies.get('hhtoken'))
    '''
    
    qs = urllib.urlencode([(key, val) 
                           for (key,val) in query_args.iteritems()
                           if val])
    
    if qs:
        return base + '?' + qs
    else:
        return base 

class Session:
    def __init__(self, session_xml):
        self.hhid = session_xml.findtext('hhid-session/account/hhid')
        self.email = session_xml.findtext('hhid-session/account/email')
        self.user_id = session_xml.findtext('hh-session/account/user-id')
        self.user_type = session_xml.findtext('hh-session/account/user-type')
        self.lang = session_xml.findtext('locale/lang')
        self.site_id = session_xml.findtext('locale/site-id')
        self.site_code = session_xml.findtext('locale/site-code')
        self.platform = session_xml.findtext('locale/platform-code')
        self.area = session_xml.findtext('locale/area-id')

def get_session(request):
    hhtoken = request.cookies.get('hhtoken')
    hhuid = request.cookies.get('hhuid')
    
    url = make_url(config.sessionHost + 'hh-session', 
                   host = config.host,
                   hhtoken = hhtoken, 
                   hhuid = hhuid)

    session_xml = http_get(url).get()
    
    return Session(session_xml)