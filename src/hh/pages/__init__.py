# -*- coding: utf-8 -*-

from hh import Doc
from hh.http_client import http_get

import config
import util

def get_article(session, article_id):
    return http_get(config.planetahrHost + 'xml/article/' + 
                    str(article_id) + '/' + session.site_code + '/' + session.lang)

def article(request):
#  <xi:include href="xml/page.xml"/>

    result = Doc('article')
    # TODO result.set_xsl('article.xsl')

    session = util.get_session(request)
        
    result.put(get_article(session, 599))
    result.put(get_article(session, request.GET['articleId']))

#  <xi:include href="xml/banners/article.xml"/>
#  
#  <xi:include href="xml/head/full.xml"/>
#  <xi:include href="xml/data/menu.xml"/>
#  <xi:include href="xml/foot.xml"/>
#  <xi:include href="xml/translations/index.xml"/>

    return result
