## Pydevd debug handler

Frontik provides special URL `/pydevd` to invoke `pydevd.settrace()` function. It's only allowed with `debug` option
 set to True in app config.

To debug app, you should start a debug server on your host and then open `/pydevd` URL: Frontik will try to connect
 to debug server on host that made a request at port `32223`, unless other is specified.

It's not always possible to determine host IP, so, you can provide ip and port of debug server explicitly:
`/pydevd?ip=10.208.80.148&port=10050`.
