from frontik.handler import PageHandler
from frontik.validator import Validators


class Page(PageHandler):
    def get_page(self):
        string = self.get_string_argument('string')
        list_int = self.get_validated_argument('list', Validators.LIST_INT, array=True)

        self.json.put({'list': list_int, 'string': string})
