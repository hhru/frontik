# -*- coding: utf-8 -*-

from hh import Doc
from hh.http_client import http_get

import config
import util

def get_article(session, article_id):
    return http_get(config.planetahrHost + 'xml/article/' + 
                    str(article_id) + '/' + session.site_code + '/' + session.lang)

def banners_base(request):
#      local unique_banner_user = xscript.request:getCookie('unique_banner_user');
#      if unique_banner_user == '' then
#        uuid = os.time() .. math.random(10000000000000);
#
#        local c = xscript.cookie.new('unique_banner_user', uuid)
#        c:path('/');
#        c:expires(os.time() + 60 * 60 * 24);
#        xscript.response:setCookie(c)
#      end
#      xscript.state:setString('unique_banner_user', unique_banner_user);

#    if request.cookies.get('unique_banner_user'):
#        unique_banner_user = request.cookies.get('unique_banner_user')
#    else:
#        pass

    if request.params.get('professionalAreaId', '') and request.params.get('professionalAreaId', '') <> '0':
        specializationListRequestConcat = '&specializationId='.join(request.params.getall('specializationId'))

        if specializationListRequestConcat == '':
            specializationListForBanner = '' # TODO return
        else:
            specializationListForBanner = '&specializationId=' + specializationListRequestConcat
    else:
        specializationListForBanner = ''

    if request.params.get('areadId'):
        bannerArea = '&areaId=' + request.params.get('areadId')
    else:
        bannerArea = ''
        
#    uriBanner = (config.serviceHost +
#                 'bannerList?' + 
#                 'uuid=' + 
#  <x:mist>
#    <method>setStateConcatString</method>
#    <param type="String">uriBanner</param>
#    <param type="StateArg" as="String">serviceHost</param>
#    <param type="String">bannerList?</param>
#    <param type="String">uuid=</param>
#    <param type="StateArg" as="String">unique_banner_user</param>
#    <param type="String">&amp;userId=</param>
#    <param type="StateArg" as="String">userId</param>
#    <param type="String">&amp;siteId=</param>
#    <param type="StateArg" as="String">site</param>
#    <param type="String">&amp;professionalAreaId=</param>
#    <param type="QueryArg" as="String">professionalAreaId</param>
#    <param type="StateArg" as="String">specializationListForBanner</param>
#    <param type="StateArg" as="String">bannerArea</param>
#  </x:mist>
#  <x:mist>
#    <method>setStateConcatString</method>
#    <param type="String">uriBannerMulty</param>
#    <param type="StateArg" as="String">uriBanner</param>
#    <param type="String">&amp;multy=true</param>
#  </x:mist>


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
