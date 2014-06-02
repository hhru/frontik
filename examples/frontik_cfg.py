# All settings are left to default values

port = 9301

from frontik.app import App

urls = [
    (r'/example', App('example_app', './example_app')),
]
