## Content types and producers

For now there are two ways to generate content in Frontik application:

* generic ```self.text``` producer
* ```self.doc``` + XSL transformation

The first one is generally combined with setting response content type manually:

```python
self.text = 'OK'
self.set_header('Content-Type', 'text/plain')
```

This producer is used by default if ```self.text``` value is not ```None```.

Note, that if you assign ```self.text``` a dict object, the response would be encoded as application/json — this is a
useful Tornado feature.

The second alternative is producing text/html with XML and XSLT:

```python
self.doc = xml_document  # some etree-compatible element
self.set_xsl('transform.xsl')
```

The rest is done automatically. Root directory for xsl files and other parameters are set up in application config file
(see [Configuring Frontik application](/docs/config-app.md)).
