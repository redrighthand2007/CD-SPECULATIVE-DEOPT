"""
ir.py
Module owner: GUNJAL SAI SANJAY (24BCT0064) -- Prototype / Baseline Execution / Integration
Part of: BCSE307P - A31 - Speculative Optimizer with Deoptimization Support

Converts an AST into a flat, baseline (non-optimized) IR, and provides the
baseline interpreter used both for normal execution and as the deoptimization
fallback target.

Baseline opcode set (fixed at Review 1):
    LOAD_CONST <value>
    STORE <name>
    LOAD <name>
    ADD
    PRINT
"""

from src.parser import Assign, BinOp, Literal, Print, Program, Var


# ROLE: Language-level type error raised when invalid types are added (e.g. str + int).
class ToyTypeError(Exception):
    """Raised for a language-level (not a raw Python) type mismatch on '+'.
    Both the baseline and the generic (non-specialized) ADD path route
    through this so failures are always controlled and diagnosable,
    never an uncaught Python TypeError."""


# ROLE: Dynamic '+' operation: evaluates int+int or str+str, raising controlled ToyTypeError on mismatch.
def toy_add(a, b):
    if isinstance(a, int) and isinstance(b, int):
        return a + b
    if isinstance(a, str) and isinstance(b, str):
        return a + b
    raise ToyTypeError(
        f"cannot apply '+' to {type(a).__name__} ({a!r}) and {type(b).__name__} ({b!r})"
    )


# ROLE: Data class representing a single flat linear IR instruction (operation, operand, line number).
class Instr:
    __slots__ = ("arg", "line", "op")

    # ROLE: Initializes the IR instruction with opcode name, optional argument, and source line number.
    def __init__(self, op, arg=None, line=None):
        self.op = op
        self.arg = arg
        self.line = line

    def __repr__(self):
        return f"{self.op} {self.arg if self.arg is not None else ''}".strip()


# ROLE: Traverses the AST in depth-first post-order and generates linear stack-based IR instructions.
def generate_ir(program: Program):
    """Depth-first flattening of the AST into baseline IR instructions."""
    ir = []

    def gen_expr(node):
        if isinstance(node, Literal):
            ir.append(Instr("LOAD_CONST", node.value))
        elif isinstance(node, Var):
            ir.append(Instr("LOAD", node.name))
        elif isinstance(node, BinOp):
            gen_expr(node.left)
            gen_expr(node.right)
            ir.append(Instr("ADD"))
        else:
            raise ValueError(f"Unknown expression node: {node}")  # noqa: TRY004

    for stmt in program.statements:
        if isinstance(stmt, Assign):
            gen_expr(stmt.expr)
            ir.append(Instr("STORE", stmt.name, stmt.line))
        elif isinstance(stmt, Print):
            gen_expr(stmt.expr)
            ir.append(Instr("PRINT", None, stmt.line))
        else:
            raise ValueError(f"Unknown statement node: {stmt}")  # noqa: TRY004

    return ir


# ROLE: Resumable baseline VM that can restart execution at any arbitrary instruction index with restored state.
class BaselineInterpreter:
    """
    Executes baseline IR unconditionally (no speculation). Also used as the
    fallback engine that deoptimization resumes into.
    """

    # ROLE: Initializes the interpreter environment dictionary and output buffer.
    def __init__(self):
        self.env = {}
        self.output = []

    # ROLE: Executes instructions starting from instruction index 'start' with optional restored environment.
    def run(self, ir, start=0, env=None):
        """Execute ir starting at instruction index `start`.
        `env` lets the deoptimizer hand over a reconstructed variable state.
        """
        if env is not None:
            self.env = env
        stack = []
        i = start
        while i < len(ir):
            instr = ir[i]
            if instr.op == "LOAD_CONST":
                stack.append(instr.arg)
            elif instr.op == "LOAD":
                if instr.arg not in self.env:
                    raise NameError(f"Undefined variable '{instr.arg}' (line {instr.line})")
                stack.append(self.env[instr.arg])
            elif instr.op == "STORE":
                stack.pop()  # value already committed by caller during interleaved exec;
            elif instr.op == "ADD":
                b = stack.pop()
                a = stack.pop()
                stack.append(toy_add(a, b))
            elif instr.op == "PRINT":
                val = stack.pop()
                self.output.append(val)
            i += 1
        return self.output


# ROLE: Clean entry point to execute baseline IR from start to finish on a clean VM.
def run_baseline(source_ir, env=None):
    """Simple, self-contained baseline execution (used by Test-1..Test-4)."""
    interp = BaselineInterpreterSimple(env or {})
    return interp.execute(source_ir)


# ROLE: Clean, robust stack-machine baseline VM for ground-truth execution and fallback execution.
class BaselineInterpreterSimple:
    """A clean, correct baseline VM: STORE commits from the value stack."""

    # ROLE: Initializes the baseline VM with initial variable bindings and empty output.
    def __init__(self, env=None):
        self.env = dict(env or {})
        self.output = []

    # ROLE: Executes the instruction list sequentially using an operand stack and variable environment.
    def execute(self, ir):
        stack = []
        for instr in ir:
            if instr.op == "LOAD_CONST":
                stack.append(instr.arg)
            elif instr.op == "LOAD":
                stack.append(self.env[instr.arg])
            elif instr.op == "STORE":
                stack_top = stack.pop()
                self.env[instr.arg] = stack_top
            elif instr.op == "ADD":
                b = stack.pop()
                a = stack.pop()
                stack.append(toy_add(a, b))
            elif instr.op == "PRINT":
                self.output.append(stack.pop())
        return self.output


if __name__ == "__main__":
    from src.parser import parse
    prog = parse('x = 10;\ny = x + 5;\nprint(y);')
    ir = generate_ir(prog)
    for instr in ir:
        print(instr)
    print("Output:", run_baseline(ir))
