# -*- coding: utf-8 -*-

from frontik import DocResponse, http_get

import hh.config
import hh.util
import hh.head
import hh.menu
import hh.foot
import hh.translations

def get_article(session, article_id):
    if article_id:
        return http_get(hh.config.planetahrHost + 'xml/article/' + 
                        str(article_id) + '/' + session.site_code + '/' + session.lang)

def get_page(request):
    response = DocResponse('article')
    # TODO response.set_xsl('article.xsl')

    session = hh.util.get_session(request)
    
    response.doc.put(get_article(session, 599))
    response.doc.put(get_article(session, request.GET['articleId']))
    
    banners = hh.util.Banners(request, response, session)
    
    response.doc.put(banners.get_banners([137, 138, 144]))

    hh.head.do_head(response, session)

    hh.menu.do_menu(response, session)

    hh.foot.do_foot(response)
    
    response.doc.put(hh.translations.get_translations(session, hh.translations.index_translations))

    return response
