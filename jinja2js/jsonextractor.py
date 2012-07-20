from itertools import chain
from StringIO import StringIO

from jinja2.compiler import CodeGenerator, CompilerExit, Frame
import jinja2.nodes as nodes

from constprepare import prepare_const

class JSONVisitor(CodeGenerator):
    """
    Returns a compileable template that is used to return the JSON that is
    otherwise used to render the template on the client side.
    """

    def __init__(self, *args, **kwargs):
        super(JSONVisitor, self).__init__(*args, **kwargs)

        self.output_level = 0
        self.block_level = 0
        self.assigning = False
        self.paramming = False

        self.stream = StringIO()
        self.pos_id = 0

    def positional_identifier(self):
        self.pos_id += 1
        return "posid__%d" % (self.pos_id - 1)

    def blockvisit(self, nodes, frame):
        self.writeline("")
        try:
            for node in nodes:
                self.visit(node, frame)
        except CompilerExit:
            pass

    def visit(self, *args, **kwargs):
        print type(args[0])
        super(JSONVisitor, self).visit(*args, **kwargs)

    def visit_Template(self, node, frame=None):
        # We don't do all the fancy checks that Jinja does, since this is the
        # fall-forward method. If it doesn't work in Jinja, don't expect it to
        # work here.

        eval_ctx = nodes.EvalContext(self.environment, self.name)

        from jinja2.runtime import __all__ as exported
        self.writeline("from jinja2.runtime import " + ", ".join(exported))

        for import_ in node.find_all(nodes.ImportedName):
            if import_.importname not in self.import_aliases:
                imp = import_.importname
                self.import_aliases[imp] = alias = self.temporary_identifier()
                if "." in imp:
                    module, object = imp.rsplit(".", 1)
                    self.writeline("from %s import %s as %s" %
                                        (module, obj, alias))
                else:
                    self.writeline("import %s as %s" % (imp, alias))

        self.writeline("def root(context, environment):", extra=1)
        self.indent()
        #self.writeline("request = environment.request")

        body = node.body
        for block in node.find_all(nodes.Block):
            body += block.body

        frame = Frame(eval_ctx)
        frame.inspect(body)
        frame.toplevel = frame.rootlevel = True
        frame.identifiers.add_special("super")
        self.writeline("l_super = lambda *ignore: None")

        self.pull_locals(frame)
        self.pull_dependencies(body)
        self.blockvisit(node.body, frame)

        self.outdent()

    def visit_Extends(self, node, frame):
        # We don't care about "extends" in the JSON.
        pass

    # The following features are unsupported:
    def visit_Include(self, node, frame): pass
    def visit_Import(self, node, frame): pass
    def visit_FromImport(self, node, frame): pass
    def visit_Macro(self, node, frame): pass
    def visit_CallBlock(self, node, frame): pass
    def visit_FilterBlock(self, node, frame): pass
    def visit_For(self, node, frame):
        #raise Exception("`for` loops are explicitly unsupported.")
        pass

    def visit_Block(self, node, frame):
        self.block_level += 1
        self.blockvisit(node.body, frame)
        self.block_level -= 1

    def visit_Output(self, node, frame):
        # Ignore output nodes outside of blocks.
        if not self.block_level:
            return

        self.output_level += 1
        self.blockvisit(node.nodes, frame)
        self.output_level -= 1

    def visit_Assign(self, node, frame):
        self.visit_as_assignment(node, frame, body=node.node, assign_local=True)

    def visit_for_param(self, node, frame):
        self.paramming = True
        self.write("context.vars['")
        if isinstance(node, (str, unicode)):
            self.write(node.replace("'", "\\'"))
        else:
            self.visit(node, frame)
        self.write("']")
        self.paramming = False

    def visit_as_assignment(self, node, frame, target=None, body=None,
                            assign_local=False):
        # TODO: This doesn't support multiple assignments. Code will need to be
        # added to look out for Tuple objects and deal with them appropriately.

        self.assigning = True

        if assign_local:
            self.writeline("l_%s = " % node.target.name)
        else:
            self.writeline("")

        self.visit_for_param(node.target if target is None else target, frame)

        self.write(" = ")
        self.visit(node if body is None else body, frame)
        self.assigning = False

    def visit_Name(self, node, frame):
        if not self.assigning:
            return self.visit_as_assignment(node, frame, target=node.name)

        if self.paramming:
            self.write(node.name)
            return
        super(JSONVisitor, self).visit_Name(node, frame)

    def visit_Call(self, node, frame):
        if not self.assigning:
            if (isinstance(node.node, nodes.Name) and
                node.kwargs is None and
                node.args is not None and
                isinstance(node.args[0], nodes.Const) and
                node.node.name == "_"):
                return
            return self.visit_as_assignment(node, frame, target=node)

        if self.paramming:
            self.visit(node.node, frame)
            self.write("(")
            self.signature(node, frame)
            self.write(")")
            return
        super(JSONVisitor, self).visit_Call(node, frame)

    def visit_Getattr(self, node, frame):
        if not self.assigning:
            return self.visit_as_assignment(node, frame, target=node)

        if self.paramming:
            self.visit(node.node, frame)
            self.write(".")
            self.write(node.attr)
            return
        super(JSONVisitor, self).visit_Getattr(node, frame)

    def visit_Getitem(self, node, frame):
        if not self.assigning:
            return self.visit_as_assignment(node, frame, target=node)

        if self.paramming:
            self.visit(node.node, frame)
            self.write("[")
            self.visit(node.arg, frame)
            self.write("]")
            return
        super(JSONVisitor, self).visit_Getitem(node, frame)

    def visit_Const(self, node, frame):
        if self.paramming:
            data = prepare_const(node.value)
            if self.paramming:
                self.write("\\")
                data += "\\"
            self.write("'%s'" % data)
            return
        elif self.assigning:
            super(JSONVisitor, self).visit_Const(node, frame)

    def visit_TemplateData(self, node, frame):
        pass

    def visit_If(self, node, frame):
        # We need to get the values for the conditional into the JSON as well
        # as into the conditional itself.
        # TODO: This won't work well for calls/filters with side effects.
        self.visit_as_assignment(node.test, frame, target=node.test)

        if_frame = frame.soft()
        self.writeline("if ", node)
        self.assigning = True
        self.visit_for_param(node.test, frame)
        self.assigning = False
        self.write(":")

        self.indent()
        self.writeline("pass")
        self.blockvisit(node.body, if_frame)
        self.outdent()

        if node.else_:
            self.writeline("else:")

            self.indent()
            self.writeline("pass")
            self.blockvisit(node.else_, if_frame)
            self.outdent()

    def visit_Filter(self, node, frame):
        if not self.assigning:
            return self.visit_as_assignment(node, frame, target=node)

        if self.paramming:
            self.visit(node.node, frame)
            self.write("|")
            self.write(node.name)
            if node.args or node.kwargs or node.dyn_args or node.dyn_kwargs:
                self.write("(")
                self.signature(node, frame)
                self.write(")")
            return

        super(JSONVisitor, self).visit_Filter(node, frame)

    def visit_MarkSafeIfAutoescape(self, node, frame):
        if not self.assigning:
            return self.visit_as_assignment(node, frame, target=node)

        if self.paramming:
            self.write(self.positional_identifier())
            return

        super(JSONVisitor, self).visit_MarkSafeIfAutoescape(node, frame)

    def visit_Compare(self, node, frame):
        if not self.assigning:
            self.visit(node.expr, frame)
            for op in node.ops:
                self.visit(op, frame)
            return

        return super(JSONVisitor, self).visit_Compare(node, frame)

    def visit_Operand(self, node, frame):
        if not self.assigning:
            return self.visit(node.expr, frame)
        return super(JSONVisitor, self).visit_Operand(node, frame)

    def binop(operator, interceptable=True):
        def visitor(self, node, frame):
            if not self.assigning:
                return
            if self.environment.sandboxed and \
               operator in self.environment.intercepted_binops:
                self.write('environment.call_binop(context, %r, ' % operator)
                self.visit(node.left, frame)
                self.write(', ')
                self.visit(node.right, frame)
            else:
                self.write('(')
                self.visit(node.left, frame)
                self.write(' %s ' % operator)
                self.visit(node.right, frame)
            self.write(')')
        return visitor

    def uaop(operator, interceptable=True):
        def visitor(self, node, frame):
            if not self.assigning:
                return
            if self.environment.sandboxed and \
               operator in self.environment.intercepted_unops:
                self.write('environment.call_unop(context, %r, ' % operator)
                self.visit(node.node, frame)
            else:
                self.write('(' + operator)
                self.visit(node.node, frame)
            self.write(')')
        return visitor

    visit_In = binop('in')
    visit_Add = binop('+')
    visit_Sub = binop('-')
    visit_Mul = binop('*')
    visit_Div = binop('/')
    visit_FloorDiv = binop('//')
    visit_Pow = binop('**')
    visit_Mod = binop('%')
    visit_And = binop('and', interceptable=False)
    visit_Or = binop('or', interceptable=False)
    visit_Pos = uaop('+')
    visit_Neg = uaop('-')
    visit_Not = uaop('not ', interceptable=False)
    del binop, uaop

