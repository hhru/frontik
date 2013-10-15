## What is Frontik?

Frontik is an asyncronous Tornado-based application server. It was designed to support simple xml aggregation with xsl
transformation, but supports other content types as well.

Frontik was originally developed by Andrey Tatarinov at [hh.ru][hh] as a part of infrastructure development tasks.

## Documentation

* [Running Frontik](docs/running.md)
* [Configuring application — TBA](docs/configure-app.md)
* [Debugging Frontik](docs/debug.md)
* [Content types and producers](docs/producers.md)
* [Postprocessing](docs/postprocessing.md)

## How does it work?

    user   frontik   backend1 backend2 ...
    ====   =======   ======== ========
      |       |         |        |
      |------>|         |        |
      |       |         |        |
      |    (initiate requests)   |
      |       |-------->|        |
      |       |---------+------->|
      |       |----------------------->...
      |       |         |        |
      |    (wait)       |        |
      |       |<-----------------------...
      |       |<--------|        |
      |       |<--------+--------|
      |       |         |        |
      |    (xsl)        |        |
      |       |--\      |        |
      |       |  | xsl  |        |
      |       |<-/      |        |
      |       |         |        |
      |    (done)       |        |
      |<------|         |        |
      |       |         |        |

Typically page generation process is split into several steps:

  * initiate requests: frontik makes several http-requests to underlying backends
  * wait for response (or timeout) for each backend request
  * aggregate all responses and apply xsl transformation or construct result in any other way (see [Producers](docs/producers.md))
  * return the result to user after postprocessing (see [Postprocessing](docs/postprocessing.md))

## Usages

  * All pages of [hh.ru][http://hh.ru/] are served with frontik
