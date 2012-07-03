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
                         Output as OutputNode
from jinja2.parser import Parser
from jinja2.visitor import NodeVisitor


def accessor(key):
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
        self.write(self.visit(node.test))
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
        if node.args:
            first = True
            for arg in node.args:
                if not first:
                    output.write(", ")
                output.write(self.visit(arg))
                first = False

        if node.kwargs:
            first = True
            for kwarg in node.kwargs:
                if not first or node.args:
                    output.write(", ")
                output.write(self.safe_visit(kwarg))
                first = False
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

        subscript = self.visit(node.arg)
        return "%s[%s]" % (self.visit(node.node), subscript)

    def visit_Const(self, node):
        if node.value is None:
            return "null"

        if isinstance(node.value, (int, float, long, bool)):
            return str(node.value)

        output = StringIO()
        if self.paramming:
            output.write("\\")
        output.write("'")

        value = node.value.replace("\n", "\\n")
        value = value.replace("\t", "\\t")
        value = value.replace("\r", "\\r")
        value = value.replace("'", "\\'")
        output.write(value)

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
        return "(%s && %s)" % (self.visit(node.left), self.visit(node.right))

    def visit_Or(self, node):
        return "(%s || %s)" % (self.visit(node.left), self.visit(node.right))

    def visit_Not(self, node):
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
        self.start_wrapper()
        self.write(self.safe_visit(node.target))
        self.write(" = ")
        self.write(self.visit(node.node))
        self.write("; return '';")
        return self.end_wrapper()

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
        return "filter(%s, '%s')" % (self.visit(node.node), node.name)

    def visit_Slice(self, node):
        if node.step:
            raise Exception("Slice steps are not supported.")
        params = []
        params.append(node.start if node.start else 0)
        if node.end:
            params.append(node.end)
        return ".slice(%s)" % ", ".join(params)


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

