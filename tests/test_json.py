import os

import jinja2

import jinja2js


class MockRequest(object):

    def __init__(self):
        self.GET = {}
        self.POST = {}


class TestJSON(object):
    """
    Test that appropriate JSON is rendered for a given set of input.
    """

    def setUp(self):
        self.env = jinja2.Environment()
        self.loader = jinja2.FileSystemLoader(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "templates"))
        self.env.loader = self.loader

        self.env.add_extension("jinja2.ext.i18n")

    def test_json(self):
        jinja2js.set_env(self.env)
        request = MockRequest()
        data = jinja2js.extract_template(request, "app.html")
        print data
