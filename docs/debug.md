## Debug mode

Frontik supports extended debug mode. It is enabled by GET parameter 'debug' (you can also set cookie 'debug=...').
Available options:

* debug=true or debug — simple debug
* debug=full — extended debug
* debug=nopass — disables passing debug header to services
* debug=@text — highlights log entries matching 'text'

You can combine these options, for example: debug=full,nopass
