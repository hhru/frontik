## Page generation process

![Page generation scheme](/docs/page-generation.png)

Typically page generation process is split into several steps:

* run preprocessors (see [Preprocessors](/docs/preprocessors.md))
* execute handler code: parse request parameters and make some requests to backends
(see [Making HTTP requests](/docs/http-client.md))
* wait for responses (or timeouts) from each backend, run callbacks and possibly
make some more requests
* aggregate all responses and construct result in one of supported ways
(see [Producers](/docs/producers.md))
* run postprocessors and templating (see [Postprocessing](/docs/postprocessing.md))
