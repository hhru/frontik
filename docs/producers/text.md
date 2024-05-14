## Generic producer

Assign any string value to `self.text` to write it directly to the response.

```python
@router.get('/some_page', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    handler.text = 'OK'
    handler.set_header('Content-Type', media_types.TEXT_PLAIN)
```

This producer is used by default if `self.text` value is not `None`.
Note that you should also set neccessary `Content-Type` headers.
