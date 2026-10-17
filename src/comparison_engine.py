"""
comparison_engine.py
Comparative Execution and Evaluation Engine for Review 3.
Compares:
  1. Baseline Interpreter (Unoptimized Dynamic Dispatch)
  2. Unsafe Speculation WITHOUT Deoptimization (Crash / Fatal Abort)
  3. Speculative Optimization WITH Deoptimization (Our Engine)

Demonstrates:
  - Throughput (ops/sec) in stable loops
  - Crash behavior when types mutate without deoptimization
  - State reconstruction and dynamic recovery with deoptimization
  - Low-throughput / deoptimization thrashing overhead analysis
"""

import time
import sys
from src.parser import parse
from src.ir import generate_ir, BaselineInterpreterSimple, ToyTypeError, Instr
from src.optimizer import profile, speculate, GuardedInterpreter, Deoptimizer, AssumptionFailure


# ROLE: Unsafe speculative interpreter that executes optimized opcodes without deoptimization fallback.
class UnsafeSpeculationInterpreter:
    """
    Executes speculative code WITHOUT deoptimization support.
    Demonstrates what happens in a naive or unchecked speculative engine:
    when an assumption is violated, the program fatally crashes.
    """

    def __init__(self, env):
        self.env = dict(env)
        self.output = []

    def execute_blind(self, ir):
        """
        Unchecked / Blind execution: strips guard checks and blindly runs ADD_INT.
        If variable holds incompatible type, raises a raw Python fatal TypeError.
        """
        stack = []
        for instr in ir:
            if instr.op == "CHECK_INT":
                continue  # In unchecked speculation, guards are omitted
            elif instr.op == "LOAD_CONST":
                stack.append(instr.arg)
            elif instr.op == "LOAD":
                stack.append(self.env[instr.arg])
            elif instr.op == "STORE":
                self.env[instr.arg] = stack.pop()
            elif instr.op == "ADD_INT":
                # Blind integer addition: will throw fatal TypeError if operand is string
                b = stack.pop()
                a = stack.pop()
                if not (isinstance(a, int) and isinstance(b, int)):
                    raise TypeError(
                        f"FATAL VM CRASH: Raw ADD_INT executed on incompatible types "
                        f"({type(a).__name__} and {type(b).__name__}). No deoptimization mechanism."
                    )
                stack.append(a + b)
            elif instr.op == "ADD":
                b = stack.pop()
                a = stack.pop()
                stack.append(a + b)
            elif instr.op == "PRINT":
                self.output.append(stack.pop())
        return self.output

    def execute_fail_stop(self, ir):
        """
        Guarded but without deoptimization: guard catches mismatch, but has no
        fallback handler, raising an unhandled fatal AssumptionFailure.
        """
        stack = []
        for idx, instr in enumerate(ir):
            if instr.op == "LOAD_CONST":
                stack.append(instr.arg)
            elif instr.op == "LOAD":
                stack.append(self.env[instr.arg])
            elif instr.op == "STORE":
                self.env[instr.arg] = stack.pop()
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
                stack.append(a + b)
            elif instr.op == "PRINT":
                self.output.append(stack.pop())
        return self.output


# ROLE: Benchmark runner measuring execution time and throughput on type-stable loops.
def benchmark_throughput(iterations: int = 100_000):
    """
    Measures throughput (operations/second) across:
    1. Baseline Interpreter
    2. Speculation WITHOUT Deoptimization (Unsafe fast path)
    3. Speculation WITH Deoptimization (Our Engine)
    """
    src = "x = 10;\ny = x + 5;\nprint(y);"
    ast = parse(src)
    base_ir = generate_ir(ast)
    prof = profile(base_ir, {})
    opt_ir = speculate(base_ir, prof)

    # 1. Baseline Benchmark
    t0 = time.perf_counter()
    for _ in range(iterations):
        interp = BaselineInterpreterSimple({})
        interp.execute(base_ir)
    t_baseline = time.perf_counter() - t0

    # 2. Speculation WITHOUT Deoptimization (Blind / Unchecked fast path)
    t0 = time.perf_counter()
    for _ in range(iterations):
        unsafe = UnsafeSpeculationInterpreter({})
        unsafe.execute_blind(opt_ir)
    t_unsafe = time.perf_counter() - t0

    # 3. Speculation WITH Deoptimization (GuardedInterpreter)
    t0 = time.perf_counter()
    guard_checks = 0
    deopts = 0
    for _ in range(iterations):
        guarded = GuardedInterpreter({})
        try:
            guarded.execute(opt_ir)
            guard_checks += 1
        except AssumptionFailure:
            deopts += 1
    t_opt_deopt = time.perf_counter() - t0

    speedup_unsafe = (t_baseline / t_unsafe) if t_unsafe > 0 else 1.0
    speedup_deopt = (t_baseline / t_opt_deopt) if t_opt_deopt > 0 else 1.0

    return {
        "iterations": iterations,
        "baseline_time": t_baseline,
        "baseline_throughput": iterations / t_baseline if t_baseline > 0 else 0,
        "unsafe_time": t_unsafe,
        "unsafe_throughput": iterations / t_unsafe if t_unsafe > 0 else 0,
        "unsafe_speedup": speedup_unsafe,
        "deopt_time": t_opt_deopt,
        "deopt_throughput": iterations / t_opt_deopt if t_opt_deopt > 0 else 0,
        "deopt_speedup": speedup_deopt,
        "guard_checks": guard_checks,
        "deopts": deopts,
    }


# ROLE: Evaluates how each engine behaves when runtime types violate profiling assumptions.
def compare_assumption_failure():
    """
    Case: Assumption Violation with Incompatible Types.
    Program: y = x + 5; print(y);
    Profiled with x = 10 (INT).
    Executed with x = 'hello' (STRING).
    """
    src = "y = x + 5;\nprint(y);"
    ast = parse(src)
    base_ir = generate_ir(ast)
    prof = {"x": "INT"}
    opt_ir = speculate(base_ir, prof)

    exec_env = {"x": "hello"}

    # 1. Baseline
    baseline_result = {}
    try:
        interp = BaselineInterpreterSimple(exec_env)
        out = interp.execute(base_ir)
        baseline_result = {"status": "SUCCESS", "output": out, "error": None}
    except ToyTypeError as e:
        baseline_result = {"status": "CONTROLLED_ERROR", "output": None, "error": str(e)}

    # 2. Speculation WITHOUT Deoptimization (Crash)
    unsafe_result = {}
    try:
        unsafe = UnsafeSpeculationInterpreter(exec_env)
        # Attempt fail-stop or blind execution
        unsafe.execute_blind(opt_ir)
        unsafe_result = {"status": "UNEXPECTED_PASS", "output": unsafe.output, "error": None}
    except Exception as e:
        unsafe_result = {
            "status": "FATAL_CRASH",
            "exception_type": type(e).__name__,
            "error_msg": str(e),
            "recovered": False,
        }

    # 3. Speculation WITH Deoptimization (Our Engine)
    deopt_result = {}
    guarded = GuardedInterpreter(exec_env)
    try:
        out = guarded.execute(opt_ir)
        deopt_result = {"status": "OPTIMIZED_PASS", "output": out, "deopt": None}
    except AssumptionFailure as fail:
        deopt = Deoptimizer()
        meta, out = deopt.deoptimize("D001", opt_ir, base_ir, guarded.env, fail)
        deopt_result = {
            "status": "SAFELY_DEOPTIMIZED",
            "deopt_id": meta["deopt_id"],
            "reason": meta["failure_reason"],
            "controlled_error": meta["controlled_error"],
            "recovered": True,
            "variable_mapping": meta["variable_mapping"],
        }

    return {
        "scenario": "Assumption Violation (Incompatible Type: 'hello' + 5)",
        "source": src.replace("\n", " "),
        "baseline": baseline_result,
        "without_deopt": unsafe_result,
        "with_deopt": deopt_result,
    }


# ROLE: Demonstrates dynamic recovery when polymorphic alternate types are valid.
def compare_polymorphic_recovery():
    """
    Case: Polymorphic Valid Type Rescue.
    Program: y = x + suffix; print(y);
    Profiled with x = 10, suffix = 5 (INT).
    Executed with x = 'VIT', suffix = ' Vellore' (Valid STRING concatenation).
    """
    src = "y = x + suffix;\nprint(y);"
    ast = parse(src)
    base_ir = generate_ir(ast)
    prof = {"x": "INT", "suffix": "INT"}
    opt_ir = speculate(base_ir, prof)

    exec_env = {"x": "VIT", "suffix": " Vellore"}

    # 1. Baseline
    b_interp = BaselineInterpreterSimple(exec_env)
    b_out = b_interp.execute(base_ir)

    # 2. Speculation WITHOUT Deopt (Crash because ADD_INT cannot add strings)
    unsafe_result = {}
    try:
        unsafe = UnsafeSpeculationInterpreter(exec_env)
        unsafe.execute_blind(opt_ir)
        unsafe_result = {"status": "SUCCESS", "output": unsafe.output}
    except Exception as e:
        unsafe_result = {
            "status": "FATAL_CRASH",
            "exception_type": type(e).__name__,
            "error_msg": str(e),
            "recovered": False,
        }

    # 3. Speculation WITH Deopt (Recovers and produces correct string output)
    deopt_result = {}
    guarded = GuardedInterpreter(exec_env)
    try:
        out = guarded.execute(opt_ir)
        deopt_result = {"status": "OPTIMIZED", "output": out}
    except AssumptionFailure as fail:
        deopt = Deoptimizer()
        meta, out = deopt.deoptimize("D_POLY", opt_ir, base_ir, guarded.env, fail)
        deopt_result = {
            "status": "RECOVERED_TO_BASELINE",
            "output": out,
            "deopt_id": meta["deopt_id"],
            "reason": meta["failure_reason"],
            "recovered": True,
        }

    return {
        "scenario": "Polymorphic Rescue (Valid String Concat: 'VIT' + ' Vellore')",
        "baseline_output": b_out,
        "without_deopt": unsafe_result,
        "with_deopt": deopt_result,
    }


# ROLE: Analyzes degraded throughput when deoptimization is repeatedly triggered (thrashing).
def compare_deopt_thrashing(iterations: int = 5_000):
    """
    Measures the cost of deoptimization:
    When assumptions fail on every iteration (megamorphic call site), state reconstruction
    incurs measurable overhead compared to baseline dynamic dispatch.
    This explains why industrial JITs need deopt counters and bailout heuristics!
    """
    src = "y = x + 5;\nprint(y);"
    ast = parse(src)
    base_ir = generate_ir(ast)
    prof = {"x": "INT"}
    opt_ir = speculate(base_ir, prof)

    # Baseline steady dynamic execution
    t0 = time.perf_counter()
    for _ in range(iterations):
        b_interp = BaselineInterpreterSimple({"x": 10})
        b_interp.execute(base_ir)
    t_baseline = time.perf_counter() - t0

    # Pathological Deoptimization Thrashing (Deoptimizes on every single iteration)
    t0 = time.perf_counter()
    deopt_count = 0
    for _ in range(iterations):
        guarded = GuardedInterpreter({"x": "hello"})
        try:
            guarded.execute(opt_ir)
        except AssumptionFailure as fail:
            deopt_count += 1
            deopt = Deoptimizer()
            deopt.deoptimize(f"D{deopt_count}", opt_ir, base_ir, guarded.env, fail)
    t_thrashing = time.perf_counter() - t0

    slowdown = (t_thrashing / t_baseline) if t_baseline > 0 else 1.0

    return {
        "iterations": iterations,
        "baseline_time": t_baseline,
        "baseline_throughput": iterations / t_baseline if t_baseline > 0 else 0,
        "thrashing_time": t_thrashing,
        "thrashing_throughput": iterations / t_thrashing if t_thrashing > 0 else 0,
        "slowdown_factor": slowdown,
        "deopt_count": deopt_count,
    }
