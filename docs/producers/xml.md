## XML producer

This producer generates `application/xml` responses (or `text/html` with XSLT):

```python
self.doc.put(etree.Element(...))  # adds XML element
self.doc.put('some text')  # adds text content to the previous (or root) node
self.doc.put(self.xml_from_file('menu.xml'))  # adds XML elements from file
self.doc.put(self.get_url('http://localhost/resource.xml')  # adds XML response from specified resource

self.set_xsl('transform.xsl')  # uses XSL template to generate text/html instead of application/xml
```
