from lxml.builder import E

from frontik import handler, media_types
from frontik.handler import router


class Page(handler.PageHandler):
    @router.get()
    async def get_page(self):
        self.log.debug('debug: starting debug page')

        def _exception_trace() -> None:
            def _inner() -> None:
                msg = 'Testing an exception юникод'
                raise ValueError(msg)

            _inner()

        try:
            _exception_trace()
        except ValueError:
            self.log.exception('exception catched')

        self.log.warning('warning: testing simple inherited debug')
        await self.post_url(self.request.host, self.request.path)

        self.log.error('error: testing failing urls')
        await self.get_url('invalid_host', 'invalid_url')

        self.log.info('info: testing responses')
        await self.put_url(self.request.host, self.request.path + '?type=html')
        await self.put_url(self.request.host, self.request.path + '?type=protobuf')
        await self.put_url(self.request.host, self.request.path + '?type=xml')
        await self.put_url(self.request.host, self.request.path + '?type=javascript')
        await self.put_url(self.request.host, self.request.path + '?type=text')

        if self.get_argument('no_recursion', 'false') != 'true':
            self.log.debug('testing complex inherited debug')
            await self.get_url(self.request.host, self.request.path + '?no_recursion=true&debug=xslt')
        else:
            self.log.debug('testing xslt profiling')
            self.set_xsl('simple.xsl')

        self.log.debug('testing xml output', extra={'_xml': E.root(E.child1(param='тест'), E.child2('тест'))})
        self.log.debug('testing utf-8 text output', extra={'_text': 'some\nmultiline\nюникод\ndebug'})
        self.log.debug('testing unicode text output', extra={'_text': 'some\nmultiline\nюникод\ndebug'})

    @router.post()
    async def post_page(self):
        self.log.debug('this page returns json')

        self.json.put({'param1': 'value', 'param2': 'тест', 'тест': 'value'})

    @router.put()
    async def put_page(self):
        content_type = self.get_argument('type')

        if content_type == 'html':
            self.set_header('Content-Type', media_types.TEXT_HTML)
            self.text = '<html><h1>ok</h1></html>'
        elif content_type == 'protobuf':
            self.set_header('Content-Type', media_types.APPLICATION_PROTOBUF)
            self.text = 'SomeProtobufObject()'
        elif content_type == 'xml':
            self.doc.put(E.response('some xml'))
        elif content_type == 'javascript':
            self.set_header('Content-Type', media_types.APPLICATION_JAVASCRIPT)
            self.text = 'document.body.write("Привет")'
        elif content_type == 'text':
            self.set_header('Content-Type', media_types.TEXT_PLAIN)
            self.text = 'привет charset'.encode()
