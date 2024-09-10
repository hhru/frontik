import json
import yaml
from frontik.app import FrontikAsgiApp
from frontik.routing import import_all_pages


if __name__ == '__main__':
    # пизда конечно.. надо пока запарковать
    # сюда надо сложные парамы передавать 1. имя модуля где пейжи 2. папку куда перекладывать 3 релизилка должна коммитиьт


    import_all_pages('example')
    app = FrontikAsgiApp()

    openapi = app.openapi()
    version = openapi.get('openapi', 'unknown version')

    print(f'writing openapi spec v{version}')
    with open('../specanahui.json', 'w') as f:
        if app:  # if true
            json.dump(openapi, f, indent=2)
        else:
            yaml.dump(openapi, f, sort_keys=False)
    print('done')
