## Content types and producers

There are three ways to generate content in Frontik application:

* generic `self.text` producer
* `self.doc` for XML (+ XSLT as templating engine)
* `self.json` for JSON (+ Jinja2 as templating engine)

The first one is generally combined with setting response content type manually:

```python
self.text = 'OK'
self.set_header('Content-Type', 'text/plain')
```

This producer is used by default if `self.text` value is not `None`.

The second alternative is producing `application/xml` (or `text/html` with XSLT):

```python
self.doc.put(etree.Element(...))  # adds XML element
self.doc.put('<error fatal="true"/>')  # converts a string to XML element and adds it
self.doc.put(self.xml_from_file('menu.xml'))  # adds XML elements from file
self.doc.put(self.get_url('http://localhost/resource.xml')  # adds XML response from specified resource

self.set_xsl('transform.xsl')  # uses XSL template to generate text/html instead of application/xml
```

The last alternative is to generate `application/json` (or `text/html` with Jinja2 templating):

```python
self.json.put({'error': {'fatal': True}})  # adds a dict
self.doc.put({
    'news': self.get_url('http://localhost/news.json'),
    'images': self.get_url('http://localhost/images.json')
})  # adds JSON responses from specified resources

self.set_template('template.html')  # uses Jinja2 template to generate text/html
                                    # instead of application/json
```

Root directory for XSL or Jinja template files and some other parameters are set up in application config file
(see [Configuring Frontik application](/docs/config-app.md)).
