import json

import jinja2.environment
from jinja2.runtime import new_context

from jsonextractor import JSONVisitor

# This is the environment that is used. If Jingo is used to load templates, this
# will get set by set_env().
env = None

try:
    import jingo
    env = jingo.env
except ImportError:
    pass

def set_env(environment):
    global env
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
            from django.template.context import get_standard_processors
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

    ast = env._parse(source, name=None, filename=filename)
    compiler = JSONVisitor(env, name=None, filename=filename)
    compiler.visit(ast)
    gen_python = compiler.stream.getvalue()

    compiled = compile(gen_python, filename, "exec")
    namespace = {}
    exec compiled in namespace

    jinj_context = new_context(env, None, blocks={}, vars=get_context(),
                               globals=env.globals)
    namespace["root"](jinj_context, env)
    vars = jinj_context.vars
    output = {}
    for key, var in vars.items():
        if not isinstance(var, (int, float, long, str, unicode, bool)):
            var = bool(var)
        output[key] = var
    return output


try:
    from django import http
except ImportError:
    http = None

def extract(request, template, context=None, **kwargs):
    extracted = extract_template(request, template, context)
    kwargs.setdefault("content_type", "application/json")
    return http.HttpResponse(json.dumps(extracted), **kwargs)
