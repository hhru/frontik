## What is Frontik?

Frontik is an asyncronous Tornado-based application server. It was designed to support simple xml aggregation with xsl transformation, but supports other content types as well.

Frontik was originally developed by Andrey Tatarinov at [hh.ru][hh] as a part of infrastructure development tasks.

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
  * wait for either response or timeout for each backend request
  * aggregate everything we got into one xml document, apply xsl transformation (or construct result in any other way)
  * return the result of transformation to user

## Where is it used?

  * All pages of [hh.ru][hh] are served using frontik

[hh]: http://hh.ru/
