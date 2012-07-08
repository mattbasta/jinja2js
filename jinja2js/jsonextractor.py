from jinja2.compiler import CodeGenerator

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
        raise Exception("`for` loops are explicitly unsupported.")

    def visit_Block(self, node, frame):
        self.block_level += 1
        self.blockvisit(node.body)
        self.block_level -= 1

    def visit_Output(self, node, frame):
        # Ignore output nodes outside of blocks.
        if not self.block_level:
            return

        self.output_level += 1
        self.blockvisit(node.nodes)
        self.output_level -= 1

    def visit_Assign(self, node, frame):
        self.visit_as_assignment(node, frame)

    def visit_as_assignment(self, node, frame):
        # TODO: This doesn't support multiple assignments. Code will need to be
        # added to look out for Tuple objects and deal with them appropriately.

        self.assigning = True
        self.write("context.vars['")
        self.paramming = True
        self.visit(node.target, frame)
        self.paramming = False
        self.write("'] = ")
        self.visit(node.node, frame)
        self.assigning = False

    def visit_Name(self, node, frame):
        if not self.assigning:
            return self.visit_as_assignment(node, frame)

        if self.paramming:
            self.write(node.name)
            return
        super(JSONVisitor, self).visit_Name(node, frame)

    def visit_Call(self, node, frame):
        if not self.assigning:
            return self.visit_as_assignment(node, frame)

        if self.paramming:
            self.visit(node.node)
            self.write("(")
            self.signature(node, frame)
            self.write(")")
            return
        super(JSONVisitor, self).visit_Call(node, frame)

    def visit_Getattr(self, node, frame):
        if not self.assigning:
            return self.visit_as_assignment(node, frame)

        if self.paramming:
            self.visit(node.node)
            self.write(".")
            self.visit(node.attr)
            return
        super(JSONVisitor, self).visit_Getattr(node, frame)

    def visit_Getitem(self, node, frame):
        if not self.assigning:
            return self.visit_as_assignment(node, frame)

        if self.paramming:
            self.visit(node.node)
            self.write("[")
            self.visit(node.arg)
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
        super(JSONVisitor, self).visit_Const(node, frame)

