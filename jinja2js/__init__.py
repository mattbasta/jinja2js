from revrender import extract, extract_template, set_env


renderers = []

# Try to use Jingo if we have it.
try:
    import jingo
    renderers.append(jingo.render)
except ImportError:
    pass

# Use `django.shortcuts.render` if we don't.
try:
    import django.shortcuts as shortcuts
    renderers.append(shortcuts.render)
except ImportError:
    pass


def render_or_extract(request, template, context=None, **kwargs):
    if request.is_ajax():
        return extract(request, template, context, **kwargs)

    if renderers:
        return renderers[0](request, template, context, **kwargs)

    raise Exception("No renderers could be found.")

