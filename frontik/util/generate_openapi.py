import argparse
import os
import pathlib
import sys

import yaml
from fastapi.openapi.utils import get_openapi
from frontik.routing import import_all_pages, routers

def main():
    parser = argparse.ArgumentParser('generate OpenAPI spec from routes')
    parser.add_argument('--app_module_path', type=str, required=True)
    parser.add_argument('--version', type=str, required=True)
    args = parser.parse_args()

    module_path = pathlib.Path(args.app_module_path)
    docs_path = os.path.join(module_path.parent, 'docs')
    sys.path.append(str(module_path.parent))

    import_all_pages(module_path.name)
    routes = [r for rout in routers for r in rout.routes]
    openapi = get_openapi(title=f'{module_path.name} OpenAPI', version=args.version, routes=routes)
    pathlib.Path(os.path.join(os.path.abspath(docs_path)), 'openapi.yaml').write_text(yaml.dump(openapi))
