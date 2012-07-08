import json

import jinja2.environment

from jsonextractor import JSONVisitor

# This is the environment that is used. If Jingo is used to load templates, this
# will get set by set_env().
env = None

try:
    import jingo
    env = jingo.get_env()
except ImportError:
    pass

def set_env(environment):
    env = environment


def extract_template(request, template, context=None):
    """
    Extracts the values used in the template along with the rendered versions of
    those values. To be used with the output of the `compile_to_js.py` template
    compiler.
    """
    def get_context():
        c = {} if context is None else context.copy()

        try:
            from django.tempalte.context import get_standard_processors
            for processor in get_standard_processors():
                c.update(processor(request))
        except ImportError:
            pass

        return c

    if isinstance(template, jinja2.environment.Template):
        raise Exception("Pre-compiled templates may not be used with the "
                        "Jinja2JS extractor.")

    if env.loader is None:
        raise TypeError("The environment does not have a configured loader.")

    source, filename, uptodate = env.loader.get_source(env, template)

    ast = env._parse(source, filename=filename)
    compiler = JSONVisitor(env, name=None, filename=filename)
    generator = compiler.visit(ast).stream.getvalue()
    print generator


def extract(request, template, context=None, **kwargs):
    extracted = extract_template(request, template, context)
    kwargs.setdefault("content_type", "application/json")
    return http.HttpResponse(json.dumps(extracted), **kwargs)
