"""
optimizer.py
Module owner: C VISHWAJEET KUMAR (24BCE0341) -- Type/Value Analysis,
              Speculative Optimizer, Runtime Guards and Deoptimizer
Part of: BCSE307P - A31 - Speculative Optimizer with Deoptimization Support

Pipeline implemented in this module:
  1. profile(ir, sample_env)        -> observed per-variable runtime types
  2. speculate(ir, profile)         -> optimized IR with CHECK_INT / ADD_INT
  3. GuardedInterpreter.execute()   -> runs optimized IR, raises on guard fail
  4. Deoptimizer.deoptimize()       -> builds metadata + resumes baseline exec

Optimized opcode additions (beyond the Review 1 baseline set):
    CHECK_INT <name>      -- guard: fails if current binding is not int
    ADD_INT                -- unguarded, specialized integer add
"""

from src.ir import BaselineInterpreterSimple, Instr, ToyTypeError, toy_add


# ROLE: Exception raised when a runtime type violates a speculative optimization assumption.
class AssumptionFailure(Exception):
    """Raised by the guarded interpreter when a CHECK_INT guard fails."""

    # ROLE: Initializes the failure record with variable name, actual observed value, and instruction index.
    def __init__(self, var_name, actual_value, instr_index):
        self.var_name = var_name
        self.actual_value = actual_value
        self.instr_index = instr_index
        super().__init__(
            f"Guard failed for '{var_name}': expected INT, got {type(actual_value).__name__} "
            f"({actual_value!r}) at optimized instruction {instr_index}"
        )


# ROLE: Simulates execution over sample inputs to profile runtime variable types (INT, STRING, or MIXED).
def profile(ir, sample_env):
    """
    Type/Value Analysis (Review 1, Step 6).
    Simulates one baseline pass over a representative sample environment,
    committing STOREs as it goes (so a LOAD correctly sees an *earlier
    statement's* assignment in the same program), and records the type
    observed at every LOAD point that feeds an ADD.
    Returns {var_name: 'INT' | 'STRING' | 'MIXED'}.
    """
    observed = {}
    env = dict(sample_env)
    stack = []
    for instr in ir:
        if instr.op == "LOAD_CONST":
            stack.append(instr.arg)
        elif instr.op == "LOAD":
            val = env.get(instr.arg)
            stack.append(val)
            t = "INT" if isinstance(val, int) else "STRING"
            prev = observed.get(instr.arg)
            observed[instr.arg] = t if prev in (None, t) else "MIXED"
        elif instr.op == "STORE":
            env[instr.arg] = stack.pop()
        elif instr.op == "ADD":
            b = stack.pop()
            a = stack.pop()
            try:
                stack.append(a + b)
            except TypeError:
                stack.append(None)
        elif instr.op == "PRINT":
            stack.pop()
    return observed


# ROLE: Generates speculative IR: replaces generic ADD with specialized ADD_INT and inserts CHECK_INT guards.
def speculate(ir, type_profile):
    """
    Speculative Optimization (Review 1, Step 7; extended in Review 3).
    Review 3 Hardening: Guards BOTH left and right variable operands (e.g. z = x + y).
    """
    # ROLE: Helper that returns the speculated type of an operand and its variable name if applicable.
    def operand_type(instr):
        if instr.op == "LOAD_CONST":
            return ("INT" if isinstance(instr.arg, int) else "STRING", None)
        if instr.op == "LOAD":
            t = type_profile.get(instr.arg)
            return (t, instr.arg if t == "INT" else None)
        return (None, None)  # nested expression result -- not eligible

    optimized = []
    i = 0
    n = len(ir)
    while i < n:
        instr = ir[i]
        if instr.op == "ADD" and i >= 2:
            left_type, left_var = operand_type(ir[i - 2])
            right_type, right_var = operand_type(ir[i - 1])
            if left_type == "INT" and right_type == "INT":
                guard_vars = []
                for v in (left_var, right_var):
                    if v is not None and v not in guard_vars:
                        guard_vars.append(v)
                for v in guard_vars:
                    optimized.append(Instr("CHECK_INT", v, instr.line))
                optimized.append(Instr("ADD_INT", None, instr.line))
                i += 1
                continue
        optimized.append(Instr(instr.op, instr.arg, instr.line))
        i += 1
    return optimized


# ROLE: High-performance speculative VM that executes optimized IR and trips guards on type mismatch.
class GuardedInterpreter:
    """
    Executes optimized (speculative) IR. Raises AssumptionFailure the moment
    a CHECK_INT guard does not hold, instead of ever executing ADD_INT on a
    non-integer -- this is what makes the optimization safe.
    """

    # ROLE: Initializes the guarded execution environment and output buffer.
    def __init__(self, env):
        self.env = dict(env)
        self.output = []

    # ROLE: Executes speculative IR instructions, raising AssumptionFailure if any CHECK_INT guard fails.
    def execute(self, ir):
        stack = []
        for idx, instr in enumerate(ir):
            if instr.op == "LOAD_CONST":
                stack.append(instr.arg)
            elif instr.op == "LOAD":
                stack.append(self.env[instr.arg])
            elif instr.op == "STORE":
                stack_top = stack.pop()
                self.env[instr.arg] = stack_top
            elif instr.op == "CHECK_INT":
                current = self.env.get(instr.arg)
                if not isinstance(current, int):
                    raise AssumptionFailure(instr.arg, current, idx)
            elif instr.op == "ADD_INT":
                b = stack.pop()
                a = stack.pop()
                stack.append(a + b)
            elif instr.op == "ADD":
                b = stack.pop()
                a = stack.pop()
                stack.append(toy_add(a, b))
            elif instr.op == "PRINT":
                self.output.append(stack.pop())
        return self.output


# ROLE: Deoptimization coordinator: captures failure metadata, reconstructs state, and resumes baseline execution.
class Deoptimizer:
    """
    Builds deoptimization metadata on assumption failure and reconstructs
    execution on the baseline interpreter (Review 1, Steps 9-11).
    """

    # ROLE: Initializes the deoptimization event history log.
    def __init__(self):
        self.log = []

    # ROLE: Handles assumption failure: records metadata, maps IP to baseline, and restarts baseline VM.
    def deoptimize(self, deopt_id, optimized_ir, baseline_ir, guard_env, failure: AssumptionFailure):
        """
        1. Record metadata: optimized position, mapped-back baseline position,
           current variable bindings, the failed assumption and the reason.
        2. Reconstruct state at the IR/interpreter level: recovery is done at
           statement granularity.
        3. Resume on the baseline interpreter from the start of that statement.
        """
        baseline_position = self._map_to_baseline(optimized_ir, baseline_ir, failure.instr_index)
        metadata = {
            "deopt_id": deopt_id,
            "optimized_position": failure.instr_index,
            "baseline_position": baseline_position,
            "variable_mapping": dict(guard_env),
            "assumption": f"{failure.var_name} is INT",
            "failure_reason": (
                f"type mismatch: '{failure.var_name}' held "
                f"{type(failure.actual_value).__name__} ({failure.actual_value!r})"
            ),
        }
        self.log.append(metadata)

        # State reconstruction + baseline fallback: re-run the failing statement on baseline VM
        baseline_interp = BaselineInterpreterSimple(guard_env)
        remaining = baseline_ir[baseline_position:]
        try:
            output = baseline_interp.execute(remaining)
            metadata["controlled_error"] = None
        except ToyTypeError as e:
            metadata["controlled_error"] = str(e)
            output = baseline_interp.output  # whatever was safely printed before the error
        return metadata, output

    # ROLE: Maps the failing optimized instruction index back to the start of the enclosing baseline statement.
    @staticmethod
    def _map_to_baseline(optimized_ir, baseline_ir, opt_index):
        failing_line = optimized_ir[opt_index].line
        for idx, instr in enumerate(baseline_ir):
            if instr.line == failing_line:
                return idx
        return 0


if __name__ == "__main__":
    from src.ir import generate_ir
    from src.parser import parse

    prog = parse('x = 10;\ny = x + 5;\nprint(y);')
    base_ir = generate_ir(prog)
    prof = profile(base_ir, {})
    opt_ir = speculate(base_ir, prof)
    print("Profile:", prof)
    print("Optimized IR:")
    for instr in opt_ir:
        print(" ", instr)
