from frontik import make_url 

import frontik_www.config

head_translations = [
    'counter.rambler',
    'counter.AdFox.firstPage',
    
    'counter.article.head',
    
    # TODO copy/paste everything from translations/head.xml 
]

loginform_translations = [
    'button.login',
    'login.enterSite',
    
    # TODO copy/paste everything from translations/loginform.xml
]

employerhelpbar_translations = [
    'employer.personal.manager.title',

    # TODO copy/paste everything from translations/employerhelpbar.xml
]

foot_translations = [
    'foot.press',
    
    # TODO copy/paste everything from translations/foot.xml
]

errors_translations = [
    'error.password.mismatch',
    
    # TODO copy/paste everything from translations/errors.xml
]

month_translations = [
    'genitive.month.01',
    
    # TODO copy/paste everything from translations/month.xml
]

hot_translations = [
    'leftMenu.yourAttention'
]

page_translations = [
    'vacancySearch.infoBlock',
    'counter.rambler',
    
    # TODO copy/paste everything from translations/page.xml
] + (
    head_translations +
    loginform_translations +
    employerhelpbar_translations +
    foot_translations +
    errors_translations +
    month_translations +
    hot_translations 
)

index_translations = [
    'index.title',
    
    # TODO copy/paste everything from translations/index.xml
] + page_translations

def get_translations(handler, translations_list):
    return handler.fetch_url(make_url(frontik_www.config.trlHost + 'translationList',
                                      site=handler.session.site_id,
                                      lang=handler.session.lang,
                                      t=translations_list)) 