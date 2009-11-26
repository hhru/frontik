# -*- coding: utf-8 -*-

import frontik
from frontik import make_url

import frontik_www.config as config
import frontik_www.handler
import frontik_www.util
import frontik_www.head
import frontik_www.menu
import frontik_www.foot
import frontik_www.translations

class Page(frontik_www.handler.SessionPageHandler):
    def get_article(self, article_id):
        if article_id:
            return self.fetch_url(frontik_www.config.planetahrHost + 'xml/article/' + 
                                  str(article_id) + '/' + self.session.site_code + '/' + 
                                  self.session.lang)

    def get_page(self):
        # TODO response.set_xsl('article.xsl')
        
        self.doc.put(self.get_article(599))
        self.doc.put(self.get_article(self.get_argument('articleId')))
        
        banners = frontik_www.util.Banners(self)
        self.doc.put(banners.get_banners([137, 138, 144]))

        frontik_www.head.do_head(self)
        
        frontik_www.menu.do_menu(self)
        
        frontik_www.foot.do_foot(self)
        
        frontik_www.translations.do_translations(self, frontik_www.translations.index_translations)
