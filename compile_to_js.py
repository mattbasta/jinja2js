"""
Jinja2JS

Usage:
  compile_to_js.py <template> [--attributes]

Options:
  --attributes      This flag will print all the JSON fields that are used by
                    the template.
"""

from cStringIO import StringIO
from docopt import docopt
import json

from jinja2.environment import Environment
from jinja2.nodes import Block as BlockNode, Name as NameNode, \
                         Output as OutputNode, Slice as SliceNode
from jinja2.parser import Parser
from jinja2.utils import is_python_keyword
from jinja2.visitor import NodeVisitor

from jinja2js.constprepare import prepare_const

def accessor(key):
    return key
    # We're going to ignore the rest of this for now.
    idx = key.find('(')
    call = ''
    if idx:
        call = key[idx:]
        key = key[:idx]
    return "']['".join(key.split('.')) + call


class JSVisitor(NodeVisitor):

    def __init__(self, attributes=False):
        self.extends = None
        self.paramming = False
        self.attributes = attributes

        self.wrappers = []

    def visit(self, *args, **kwargs):
        output = super(JSVisitor, self).visit(*args, **kwargs)
        if output is None:
            return "null"
        return output

    def write(self, js):
        top = self.wrappers[-1]
        if isinstance(top, list):
            top.append(js)
        else:
            top.write(js)

    def start_wrapper(self, wrap=True):
        self.wrappers.append(StringIO())
        if wrap:
            self.write("function(){")

    def end_wrapper(self, wrap=True):
        if wrap:
            self.write("}()")
        wrapper = self.wrappers.pop()
        return wrapper.getvalue()

    def safe_visit(self, node):
        if not self.paramming:
            self.paramming = True
            self.start_wrapper(wrap=False)
            self.write("param['")
            self.write(accessor(self.visit(node)))
            if self.attributes:
                print accessor(self.visit(node))
            self.write("']")
            self.paramming = False

            output = self.end_wrapper(wrap=False)
            return output
        else:
            return self.visit(node)

    def block_visit(self, nodes):
        self.wrappers.append([])
        for node in nodes:
            value = self.visit(node)
            if value == "":
                continue
            if value != "null":
                self.write(value)

        block = self.wrappers.pop()
        return " + ".join(block)

    def run(self, body):
        blocks = {}
        output = []
        for node in body:
            if isinstance(node, OutputNode):
                continue
            if isinstance(node, BlockNode):
                blocks[node.name] = self.block_visit(node.body)
                continue
            output.append(self.visit(node))

        if output:
            blocks["__default__"] = " + ".join(output)

        output = StringIO()
        output.write("function template(param) {return {")
        first = True
        for block, generator in blocks.items():
            if not first:
                output.write(", ")
            output.write(block)
            output.write(": function() {return ")
            output.write(generator)
            output.write(";}")
            first = False

        output.write("};}")
        return output.getvalue()

    def visit_Extends(self, node):
        # TODO: We should really do something with this someday.
        self.extends = node.template.value

    def visit_If(self, node):
        self.start_wrapper()
        self.write("if(")
        self.write(self.safe_visit(node.test))
        self.write(") {return ")
        self.write(self.block_visit(node.body))
        self.write(";}")
        if node.else_:
            self.write("else{return ")
            self.write(self.block_visit(node.else_))
            self.write(";}")
        else:
            self.write("else{return '';}")

        return self.end_wrapper()

    def visit_CondExpr(self, node):
        self.start_wrapper()
        self.write("return ")
        self.write(self.visit(node.test))
        self.write(" ? ")
        self.write(self.visit(node.expr1))
        self.write(" : ")
        if node.expr2:
            self.write(self.visit(node.expr2))
        else:
            self.write("''")
        self.write(";")
        return self.end_wrapper()

    def visit_Call(self, node):
        if isinstance(node.node, NameNode) and node.node.name == "_" and not self.paramming:
            return "gettext('%s')" % node.args[0].value.replace("'", "\\'")

        if not self.paramming:
            return self.safe_visit(node)

        output = StringIO()
        output.write(self.safe_visit(node.node))
        output.write("(")
        output.write(self.signature(node))
        output.write(")")
        return output.getvalue()

    def visit_Keyword(self, node):
        if not self.paramming:
            return self.safe_visit(node)

        return "%s=%s" % (node.key, self.safe_visit(node.value))

    def visit_Name(self, node):
        if not self.paramming:
            return self.safe_visit(node)

        return node.name

    def visit_Getattr(self, node):
        if not self.paramming:
            return self.safe_visit(node)

        return "%s.%s" % (self.safe_visit(node.node),
                          node.attr if isinstance(node.attr, str) else
                              self.safe_visit(node.attr))

    def visit_Getitem(self, node):
        if not self.paramming:
            return self.safe_visit(node)

        if isinstance(node.arg, SliceNode):
            return self.visit(node.node) + self.visit(node.arg)
        subscript = self.visit(node.arg)
        return "%s[%s]" % (self.visit(node.node), subscript)

    def visit_Const(self, node):
        if node.value is None:
            return "null"

        if isinstance(node.value, bool):
            return str(node.value).lower()
        if isinstance(node.value, (int, float, long)):
            return str(node.value)

        output = StringIO()
        if self.paramming:
            output.write("\\")
        output.write("'")

        output.write(prepare_const(node.value))

        if self.paramming:
            output.write("\\")
        output.write("'")

        return output.getvalue()

    def visit_TemplateData(self, node):
        data = node.data

        if not data.strip():
            return ""

        while "  " in data:
            data = data.replace("  ", " ")
        while "\n " in data:
            data = data.replace("\n ", "\n")
        while "\n\n" in data:
            data = data.replace("\n\n", "\n")

        data = data.replace("\n", "\\n")
        data = data.replace("\t", "\\t")
        data = data.replace("\r", "\\r")
        data = data.replace("'", "\\'")
        data = data.replace(">\\n </", "></")

        return "'%s'" % data

    def visit_And(self, node):
        op = "and" if self.paramming else "&&"
        return "(%s %s %s)" % (self.visit(node.left), op,
                               self.visit(node.right))

    def visit_Or(self, node):
        op = "or" if self.paramming else "||"
        return "(%s %s %s)" % (self.visit(node.left), op,
                               self.visit(node.right))

    def visit_Not(self, node):
        if self.paramming:
            return "(not %s)" % self.visit(node.node)
        return "!(" + self.visit(node.node) + ")"

    def visit_Compare(self, node):
        output = StringIO()
        output.write("(")

        first = True
        for op in node.ops:
            if not first:
                output.write(" && ")
            first = False
            output.write("(")
            output.write(self.visit(node.expr))
            output.write(self.visit(op))
            output.write(")")

        output.write(")")
        return output.getvalue()

    def visit_Operand(self, node):
        return " %s %s" % (node.op, self.visit(node.expr))

    def visit_Assign(self, node):
        return None

    def visit_Output(self, node):
        return self.block_visit(node.nodes)

    def visit_Block(self, node):
        return self.block_visit(node.body)

    def visit_ExprStmt(self, node):
        return self.visit(node.node)

    def visit_FloorDiv(self, node):
        return "Math.floor(%s / %s)" % (self.visit(node.left),
                                        self.visit(node.right))

    def visit_Pow(self, node):
        return "Math.pow(%s, %s)" % (self.visit(node.left),
                                     self.visit(node.right))

    def binop(operator):
        def visitor(self, node):
            return "(%s %s %s)" % (self.visit(node.left),
                                   operator,
                                   self.visit(node.right))
        return visitor

    def uop(operator):
        def visitor(self, node):
            return "(%s %s)" % (operator, self.visit(node.node))
        return visitor

    visit_Add = binop("+")
    visit_Sub = binop("-")
    visit_Mul = binop("*")
    visit_Div = binop("/")
    visit_Mod = binop("%")

    visit_Pos = uop("+")
    visit_Neg = uop("-")
    del binop, uop

    def visit_Concat(self, node):
        return " + ".join(self.visit(node) for node in node.nodes)

    def visit_Filter(self, node):
        if not self.paramming:
            return self.safe_visit(node)

        return "%s|%s" % (self.visit(node.node), node.name)

    def visit_Slice(self, node):
        if self.paramming:
            slice = [node.start if node.start else ""]
            if node.end:
                slice.append(node.end)
            elif node.step:
                slice.append("")

            if node.step:
                slice.append(node.step)
            return "[%s]" % ":".join(slice)

        if node.step:
            raise Exception("Slice steps are not supported.")
        params = []
        params.append(node.start if node.start else 0)
        if node.end:
            params.append(node.end)
        return ".slice(%s)" % ", ".join(params)

    def signature(self, node, frame=None):
        # This function was borrowed from jinja2.compiler.Compiler.signature.
        kwarg_workaround = any(map(is_python_keyword,
                                   (x.key for x in node.kwargs)))

        output = StringIO()

        for arg in node.args:
            output.write(', ')
            output.write(self.visit(arg))

        if not kwarg_workaround:
            for kwarg in node.kwargs:
                output.write(', ')
                output.write(self.visit(kwarg))
        if node.dyn_args:
            output.write(', *')
            output.write(self.visit(node.dyn_args))

        if kwarg_workaround:
            if node.dyn_kwargs is not None:
                output.write(', **dict({')
            else:
                output.write(', **{')
            for kwarg in node.kwargs:
                output.write('%r: ' % kwarg.key)
                output.write(self.visit(kwarg.value))
                output.write(', ')
            if node.dyn_kwargs is not None:
                output.write('}, **')
                output.write(self.visit(node.dyn_kwargs))
                output.write(')')
            else:
                output.write('}')

        elif node.dyn_kwargs is not None:
            output.write(', **')
            output.write(self.visit(node.dyn_kwargs))

        return output.getvalue()

    def visit_Tuple(self, node):
        if not node.items:
            return "(, )"
        return "(%s)" % ", ".join(map(self.visit, node.items))

    def visit_List(self, node):
        return "[%s]" % ", ".join(map(self.visit, node.items))

    def visit_Dict(self, node):
        return "{%s}" % ", ".join("%s: %s" % (self.visit(node.key),
                                              self.visit(node.value)) for
                                  node in node.items)


if __name__ == "__main__":
    arguments = docopt(__doc__, version="Jinja2JS 0.1")

    def parse(data):
        e = Environment()
        e.add_extension("jinja2.ext.i18n")
        return e.parse(data)

    with open(arguments["<template>"]) as fd:
        ast = parse(fd.read())

    tr = JSVisitor(attributes=arguments["--attributes"])
    output = tr.run(ast.body)
    if not arguments["--attributes"]:
        print output

