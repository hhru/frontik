What is Frontik?
================

Frontik is a simple xml aggregator for Yandex-like page generation workflow.

Frontik is developed and mantained by me (Andrey Tatarinov, elephantum@yandex.ru) while working at [hh.ru][hh] as a part of infrastructure development tasks.

How does it work?
=================

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

  1. initiate requests: frontik makes several http-requests to underlying backends.
  * wait for either response or timeout for each backend request
  * aggregate everything we got into one xml document, apply given xsl transformation
  * return the result of transformation to user.

Where is it used?
=================

  * Some of the pages of [hh.ru][hh] are served using frontik
  * [hh.jsx.ru][hhjsx] is served entirely using frontik, with [sources][hhjsxsrc] available.

[hh]: http://hh.ru/
[hhjsx]: http://hh.jsx.ru/
[hhjsxsrc]: http://github.com/AndrewSumin/hephaestus