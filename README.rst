Jinja2JS
========

Usage
-----

    python compile_to_js.py <path to jinja2 template>

The above command will yield a JavaScript function which, when executed with a
JSON blob containing values that correspond to the values requested by the
template as the first argument, will yield a rendered version of the template.

Adding the ``--attributes`` flag to the command will return a list of values
which the template expects to be provided in the JSON. This list may be more
useful if piped through ``| sort | uniq``.

Unsupported Jinja Features
--------------------------

As of the latest version, the following features are unimplemented or not
supported:

- Template inheritance (the content of each declared block is returned).
- Imports
- Includes
- Filters and filter blocks
- ``for`` loops
- Macros
- Call blocks
- Inline ``dict``s, ``tuple``s, and ``list``s.
- Some slice features (step)
- Tests

Considerations
--------------

- Content that it output outside of a block is placed in the ``__default__``
  block.
- Filters are wrapped in the ``j2filter("node", "filter_name")`` function.
  Evaluating ``"node"`` as its corresponding object in the context and applying
  the filter ``environment.filters.get("filter_name")`` will yield the expected
  result.

