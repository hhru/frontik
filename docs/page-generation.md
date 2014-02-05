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
      |  (templating)   |        |
      |       |--\      |        |
      |       |  |      |        |
      |       |<-/      |        |
      |       |         |        |
      |    (done)       |        |
      |<------|         |        |
      |       |         |        |

Typically page generation process is split into several steps:

  * initiate requests: Frontik makes several HTTP requests to underlying backends (see [Making HTTP requests](/docs/http-client.md))
  * wait for responses (or timeouts) from each backend, run callbacks and possibly make some more requests
  * aggregate all responses and run templating or construct result in any other way (see [Producers](/docs/producers.md))
  * return the result to user after postprocessing (see [Postprocessing](/docs/postprocessing.md))
