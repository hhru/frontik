# -*- coding: utf-8 -*-

from frontik import etree as et
from frontik import Doc, make_url

import frontik_www.config

career_menu = et.fromstring(
'''<careerMenu>
    <item href="/applicant/searchvacancy.xml">Вакансии</item>
    <item href="/web/guest/catalog">Компании</item>
    <item href="http://edu.hh.ru/">Образование</item>
    <item href="/web/guest/events">Календарь</item>
    <item href="/web/guest/library">Статьи</item>
    <item href="http://livehh.ru/soobshmolspetsicaru/">Общение</item>
    <item href="/web/guest/consult">Консультант</item>
    <item href="/web/guest/referat">Рефераты</item>
  </careerMenu>''')
  
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
    
    menu_doc.put(career_menu)
    
    handler.doc.put(menu_doc)
