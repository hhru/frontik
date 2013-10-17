## Page generation process

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
