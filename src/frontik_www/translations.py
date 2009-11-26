from frontik import make_url 

import frontik_www.config

head_translations = [
'counter.rambler',
'counter.AdFox.firstPage',

'counter.article.head',
'counter.index.head',

'contents.footer.employers',
'contents.footer.applicants',
'contents.footer.agencyes',

'menubar.startcareere',
'menubar.newresume',
'employer.vacancyes',

'site.russia',
'site.ukraine',
'site.kz',
'site.by',

'head.contacts',
'head.siteurl',
'header.YourCity',
'header.menuCaptionWhenNotCitySite',

'statistics.global.title',
'statistics.global.vacancy',
'statistics.global.resume',
'statistics.global.company',

'topmenu.company',
'topmenu.user',
'topmenu.logout',

'header.logo.alttext',
'header.region.youregion',

'header.langselector',
'header.langselector.ru',
'header.langselector.en',

'header.helplink',

'header.region.site.hh.ru',
'header.region.site.moscow.hh.ru',
'header.region.site.spb.hh.ru',
'header.region.site.voronezh.hh.ru',
'header.region.site.kazan.hh.ru',
'header.region.site.krasnodar.hh.ru',
'header.region.site.krasnoyarsk.hh.ru',
'header.region.site.nn.hh.ru',
'header.region.site.novosibirsk.hh.ru',
'header.region.site.rostov.hh.ru',
'header.region.site.samara.hh.ru',
'header.region.site.ural.hh.ru',
'header.region.site.yaroslavl.hh.ru',
'header.region.site.hh.ua',
'header.region.site.hh.by',
'header.region.site.headhunter.com.kz',

'header.region.site.kiev.hh.ua',
'header.region.site.donetsk.hh.ua',
'header.region.site.dnepropetrovsk.hh.ua',
'header.region.site.kharkov.hh.ua',
'header.region.site.odessa.hh.ua',
'header.region.site.lviv.hh.ua',

'header.index.meta.description',
'header.index.meta.keywords',
]

loginform_translations = [
'button.login',
'login.enterSite',
'login.enter',
'login.email',
'login.password',
'login.register',
'contents.prompt.forgetPassword.jl',
'contents.prompt.remember.jl',
'contents.prompt.forgetPassword',
'contents.prompt.remember',
'leftMenu.newUser.register',
'leftMenu.newUser.applicant',
'leftMenu.newUser.addResumeInLoginForm',
'leftMenu.newUser.directEmployer',
'leftMenu.newUser.agency',
'login.cookieFail',
'login.cookieFail.description',
]

employerhelpbar_translations = [
'employer.personal.manager.title',
'contents.login',
'from',
'leftMenu.yourManager.phone',
'leftMenu.yourManager.icq',
'leftMenu.yourManager.email',
'leftMenu.clientNumber',
'manager.assistant.deputy',
'Cancel',
'Today',
'Tomorrow',
'leftMenu.order.call',
'leftMenu.call.ordered',
'leftMenu.order.call.title',
'leftMenu.order.call.hint',
'leftMenu.order.call.PhoneNumber',
'leftMenu.order.call.PhoneTheme',
'leftMenu.order.call.PhoneTime',
'leftMenu.order.call.Desc',
'leftMenu.order.call.Order',
'leftMenu.order.call.Error',
]

foot_translations = [
'foot.press',
'foot.about',
'foot.research',
'foot.callabck',
'foot.callback',
'foot.cr',

'contents.footer.applicants',
'contents.footer.employers',
'contents.footer.agencyes',
'headhunter.reclame.title',
'requirements.title',
'contents.footer.presscenter',
'contents.footer.about',
'contents.footer.research',
'contents.footer.calendar',
'leftMenu.feedback',
'footer.headhunter.partners',

'footer.counter',
'counter.article.foot',
'counter.index.foot',

'footer.jl.about',
'footer.jl.applicants',
'footer.jl.employers',
'footer.jl.feedback',
'footer.jl.rss',
'footer.jl.advertisement',
'footer.jl.copyright',

'footer.adv.text',
]

errors_translations = [
'error.password.mismatch',
'error.login.userBlocked',
'error.companyNotApprovedYet',
    
'error.password.oldLogon.beforeEmail',
'error.password.oldLogon.afterEmail',
    
'xsl.generic.invoke.error',
'autosearches.invoke.error',
]

month_translations = [
'genitive.month.01',
'genitive.month.02',
'genitive.month.03',
'genitive.month.04',
'genitive.month.05',
'genitive.month.06',
'genitive.month.07',
'genitive.month.08',
'genitive.month.09',
'genitive.month.10',
'genitive.month.11',
'genitive.month.12',
]

hot_translations = [
    'leftMenu.yourAttention'
]

page_translations = [
'vacancySearch.infoBlock',
'counter.rambler',
'counter.AdFox.firstPage',
'leftMenu.logout',
'direct.site',
'search.advancedSearch',
    
    
'leftMenu.yourAttention',
    
'links.newResume.text',
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
'joblist.wellcome',

'index.publicationsTitle',
'index.newsTitle',
'index.newsLink',
'index.newsAccents',
'index.readMore',
'firstpage.employerslist.other',
'firstpage.employerslist.title',

'loginForm.newApplicant.register',

'hrbrand.winner',
'hrbrand.nominant',

'vacancySearch.keyword',

'button.search',
'firstPage.extendedSearch',
'firstPage.inProfessionalArea',

'firstPage.teaser.title',
'firstPage.teaser.body',

'leftMenu.textUnderBanner',

'contents.articleOfTheDay',
'index.about.header',
'index.about.body',
'index.contacts.header',
'index.contacts.body',

'index.search.tabs.searchVacancies',
'index.search.tabs.searchApplicants',
'index.search.tabs.advice',
'index.search.tabs.education',
'index.search.tabs.companyResponses',
'index.search.tabs.tests',

'index.search.applicant.hint.text',
'index.search.applicant.hint.one',
'index.search.applicant.hint.two',

'index.search.employer.hint.text',
'index.search.employer.hint.one',
'index.search.employer.hint.two',

'index.search.advices.hint.text',
'index.search.advices.hint.one',
'index.search.advices.hint.two',

'index.search.education.hint.text',
'index.search.education.hint.one',
'index.search.education.hint.two',

'index.search.applicant.submit',
'index.search.employer.submit',
'index.search.advices.submit',
'index.search.education.submit',

'index.forEmployers',
'index.needHelp',
'index.makeResume',
'index.makeVacancy',
'index.advancedSearch',
'index.salary',
'index.jobsInCompanies',
'index.palnetaHR',
'index.news',

'statistics.global.vacancy.one',
'statistics.global.vacancy.some',
'statistics.global.vacancy.many',

'statistics.global.company.one',
'statistics.global.company.some',
'statistics.global.company.many',

'statistics.global.invitation.one',
'statistics.global.invitation.some',
'statistics.global.invitation.many',
    
'index.fpblock.salary.from',
'index.fpblock.salary.to',

'index.firstpage.noscript',

'footer.adv.text',

'joblist.index.cloud',
'footer.jl.about',
'footer.jl.applicants',
'footer.jl.employers',
'footer.jl.feedback',
'footer.jl.rss',
'footer.jl.advertisement',
'footer.jl.copyright',
] + page_translations

def do_translations(handler, translations_list):
    def make_urls():
        base_url = make_url(frontik_www.config.trlHost + 'translationList',
                            site=handler.session.site_id,
                            lang=handler.session.lang)

        tr_iter = iter(translations_list)
        cont = True

        while cont:
            try:
                url = base_url
                while len(url) < 2000:
                    t = tr_iter.next()
                    url += '&t=' + t
                yield url
            except StopIteration:
                yield url
                cont = False

    for url in make_urls():
        handler.doc.put(handler.fetch_url(url))

