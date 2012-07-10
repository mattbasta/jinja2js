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

        self.request = MockRequest()
        jinja2js.set_env(self.env)

    def test_name(self):
        ctx = {"foo": "abc"}
        data = jinja2js.extract_template(self.request, "name.html", ctx)
        print data
        assert data["foo"] == "abc"

    def test_getitem(self):
        ctx = {"foo": {"bar": "basta"}}
        data = jinja2js.extract_template(self.request, "getitem.html", ctx)
        print data
        assert data["foo['bar']"] == "basta"

    def test_getattr(self):
        self.request.GET["foo"] = "bar"
        ctx = {}
        data = jinja2js.extract_template(self.request, "getattr.html", ctx)
        print data
        assert data["request.GET['foo']"] == "bar"

    def test_condexpr(self):
        ctx = {
            "foo": "abc",
            "bar": 1,
            "zap": 123,
        }

        data = jinja2js.extract_template(self.request, "condexpr.html", ctx)
        print data
        assert data["fooifbarelsezap"] == "abc"

