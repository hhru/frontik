# -*- coding: utf-8 -*-

from frontik import DocResponse, http_get

import frontik_www.config
import frontik_www.util
import frontik_www.head
import frontik_www.menu
import frontik_www.foot
import frontik_www.translations

def get_article(session, article_id):
    if article_id:
        return http_get(frontik_www.config.planetahrHost + 'xml/article/' + 
                        str(article_id) + '/' + session.site_code + '/' + session.lang)

def get_page(request):
    response = DocResponse('article')
    # TODO response.set_xsl('article.xsl')

    session = frontik_www.util.get_session(request)
    
    response.doc.put(get_article(session, 599))
    response.doc.put(get_article(session, request.GET['articleId']))
    
    banners = frontik_www.util.Banners(request, response, session)
    
    response.doc.put(banners.get_banners([137, 138, 144]))

    frontik_www.head.do_head(response, session)

    frontik_www.menu.do_menu(response, session)

    frontik_www.foot.do_foot(response)
    
    response.doc.put(frontik_www.translations.get_translations(session, frontik_www.translations.index_translations))

    return response
