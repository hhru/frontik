## JSON producer

This producer generates `application/json` responses (or `text/html` with Jinja2 templating):

```python
self.json.put({'error': {'fatal': True}})  # adds a dict
self.json.put({
    'news': self.get_url('http://localhost/news.json'),
    'images': self.get_url('http://localhost/images.json')
})  # adds JSON responses from specified resources

self.set_template('template.html')  # uses Jinja2 template to generate text/html
                                    # instead of application/json
```

Root directory for XSL or Jinja template files and some other parameters are set up in application config file
(see [Configuring Frontik application](/docs/config-app.md)).
