## Content types and producers

There are three ways to generate content in Frontik application:

* [Generic producer](/docs/producers/text.md) (`self.text`)
* [XML producer](/docs/producers/xml.md) (with XSLT as templating engine)
* [JSON producer](/docs/producers/json.md) (with Jinja2 as templating engine)

You can use any properly configured producer in your handlers, though using more than one is probably a bad idea.
In the latter case generic producer has the highest and JSON producer has the lowest priority.

The output of producers is then passed to a chain of template postprocessors
(see [Postprocessing](/docs/postprocessing.md).
