0.21.8 → 1.0
===========

В этой версии добавлена важная функциональность по поддержке больше чем одного приложения внутри фронтика.
Так как до этого момента все фронтики обслуживали ровно одно приложение, то миграция сводится к следующему:

Старый `/etc/frontik/frontik.cfg`:

    ...
    document_root = "/home/hh/hh.ru/xhh"
    app_package = "frontik_www"

Новый:

    ...
    apps = {
         "page": "/home/hh/hh.ru/xhh/frontik_www",
    }

Интерпретация URL'ов
--------------------

`apps` - отображение URL-префиксов на путь в файловой системе. Т.е. в при запросе к фронтику вида: `/page/applicant/searchvacancyresult/` будет использоваться строка конфига `"page": "/home/hh/hh.ru/xhh/frontik_www"` и для обработки запроса будет использоваться класс `Page` из файла `/home/hh/hh.ru/xhh/frontik_www/page/applicant/searchvacancyresult.py`

Импортирование модулей внутри приложения
----------------------------------------

С переходом на версию 0.22 встроенная python-инструкция `import` перестает работать для модулей внутри приложения (т.к. `import` ожидает глобальную уникальность имен модулей, чего мы не можем гарантировать для множественных приложений).

Поэтому введена новая глобальная функция, которая *автомагически* доступна во всех модулях приложений: `frontik_import(module_name)`.

Миграция:

    from frontik_www import utils
    import frontik_www.banners as banners

в:

    frontik_import('utils')
    frontik_import('banners')

**Перестало поддерживаться 1**:

    import frontik_www.banners
    ...
    frontik_www.banners.do_banners(...)

надо:

    frontik_import('banners')
    ...
    banners.do_banners(...)

**Перестало поддерживаться 2**:

    from frontik_www.handler import session
    ...
    @session

надо:

    frontik_import('handler')
    ...
    @handler.session
