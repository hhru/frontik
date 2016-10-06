## Generic producer

Assign any string value to `self.text` to write it directly to the response.

```python
class Page(frontik.PageHandler):
    def get_page(self):
        self.text = 'OK'
        self.set_header('Content-Type', 'text/plain')
```

This producer is used by default if `self.text` value is not `None`.
Note that you should also set neccessary `Content-Type` headers.
