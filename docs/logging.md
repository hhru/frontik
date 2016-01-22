## Logging in Frontik

Frontik has several options for logging:

* Writing to stderr (useful in development environment)
* Writing to a file
* Sending messages to syslog (preferred for highload projects)

For more information on configuring logging options see [Configuring Frontik](/docs/config.md).

Frontik can also send all unhandled runtime exceptions to Sentry, if `sentry_dsn` option is set in the configuration file.
Note that if you raise `tornado.web.HTTPError` in your code, it would not be sent to Sentry, because probably it's a
part of the normal flow for generating error responses.

You can also send exceptions and messages to Sentry manually:

```python
# Sending an exception to Sentry
self.get_sentry_logger().capture_exception(exc_info=(typ, value, tb))

# Sending a message to Sentry
self.get_sentry_logger().capture_message('Message for Sentry')
```

To provide Sentry logger customization, you can use `initialize_sentry_logger` method in the request handler.
It is called when Sentry logger is used first time during the request to log some exception and takes
this newly created instance of the logger as the only parameter:

```python
class Page(frontik.handler.PageHandler):
    def initialize_sentry_logger(self, sentry_logger):
        pass
```
