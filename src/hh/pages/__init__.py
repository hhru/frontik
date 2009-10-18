# -*- coding: utf-8 -*-

from hh import Page
from hh.http_client import http_get

import page

def get_article(site_code, lang, article_id):
    return http_get(page.planetahrHost + 'xml/article/' + str(article_id) + '/' + str(site_code) + '/' + str(lang))

def article(request):
    page = Page('page')

    page.put(get_article(page.siteCode, page.lang, 599).get())
    
    page.put(get_article(page.siteCode, page.lang, request.GET['articleId']).get())
            
    return page
