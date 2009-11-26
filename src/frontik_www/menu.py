# -*- coding: utf-8 -*-

from frontik import etree as et
from frontik import Doc, make_url

import frontik_www.config

def do_menu(handler):
    menu_doc = Doc('leftMenu')
    
    if handler.session.user_type == 'applicant':
        menu_doc.put(handler.fetch_url(make_url(frontik_www.config.serviceHost + 'applicant/leftMenuBar', 
                                                site=handler.session.site_id,
                                                lang=handler.session.lang)))
    else:
        menu_doc.put(handler.fetch_url(make_url(frontik_www.config.serviceHost + 'leftMenuBar',
                                                userId=handler.session.user_id,
                                                site=handler.session.site_id,
                                                lang=handler.session.lang)))

    if handler.session.platform == 'JOBLIST':
        menu_doc.put(handler.fetch_url(frontik_www.config.serviceHost + 'vacancyblocks?' +
                                       'totalCount=4&hotCount=100'))
    
    menu_doc.put(handler.xml_from_file('frontik_www/career_menu.xml'))
    
    handler.doc.put(menu_doc)
