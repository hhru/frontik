from setuptools import setup

setup(
    name = "frontik",
    version = __import__("frontik").__version__,
    description = "Frontik is a simple xml aggregator for Yandex-like page generation workflow",
    long_description = open("README.md").read(),
    url = "https://github.com/hhru/frontik",
    packages = ["frontik", "frontik/testing", "frontik/testing/pages"],
    scripts = ["scripts/frontik"],
    package_data = {
        "frontik": ["*.xsl"],
    },
    install_requires = [
        "lxml >= 2.2.8, < 2.3a",
    ],
    zip_safe = False
)
