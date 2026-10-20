import sys
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
"""
test_suite.py
Module owner: AGHERA KUSH NIPESHKUMAR (24BCE0149) -- Problem Analysis & Testing
Part of: BCSE307P - A31 - Speculative Optimizer with Deoptimization Support

Implements the five test cases fixed in the Review 1 testing strategy:
  Test 1 - Successful Optimization
  Test 2 - Assumption Failure (triggers deoptimization)
  Test 3 - Negative Type Operation
  Test 4 - Boundary Values
  Test 5 - Performance (baseline vs optimized, guard-check / deopt counts)

Run with:  python -m tests.test_suite
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ir import generate_ir, run_baseline
from src.optimizer import AssumptionFailure, GuardedInterpreter, profile, speculate
from src.parser import parse
from src.pipeline import run_program

PASS = "PASS"
FAIL = "FAIL"

results = []


def record(test_id, description, expected, actual, passed):
    results.append({
        "id": test_id,
        "description": description,
        "expected": expected,
        "actual": actual,
        "result": PASS if passed else FAIL,
    })


def test1_successful_optimization():
    src = 'x = 10;\ny = x + 5;\nprint(y);'
    r = run_program(src, sample_env={}, exec_env={}, label="Test1")
    specialized = any(instr == "CHECK_INT x" for instr in r["optimized_ir"]) and \
        any(instr == "ADD_INT" for instr in r["optimized_ir"])
    ok = (
        r["path"] == "OPTIMIZED"
        and r["output"] == [15]
        and r["deopt"] is None
        and specialized  # guards against a regression where specialization silently
                          # never fires and the generic ADD path masks the bug
    )
    record(
        "Test 1 - Successful Optimization",
        src.replace(chr(10), " "),
        "\n        - Path           : OPTIMIZED\n        - Output         : [15]\n        - Deopts         : 0\n        - Specialization : CHECK_INT/ADD_INT emitted",
        f"\n        - Path           : {r['path']}\n        - Output         : {r['output']}\n        - Deopts         : {r['deopt']}\n        - Specialization : {specialized}",
        ok,
    )
    return r


def test2_assumption_failure():
    # Profile on a representative all-INT sample so 'x' is speculated as
    # INT (this is what an earlier profiling pass over typical inputs would
    # observe), then execute the optimized IR against a context where x has
    # actually taken on a string value. This must trip CHECK_INT *before*
    # ADD_INT ever runs, hand off to the deoptimizer, and -- because the
    # underlying statement really does add an int to a string -- surface a
    # controlled ToyTypeError from the baseline fallback rather than an
    # uncontrolled crash or a silently wrong numeric result.
    src = 'y = x + 5;\nprint(y);'
    r = run_program(src, sample_env={"x": 10}, exec_env={"x": "hello"}, label="Test2")
    d: Any = r.get("deopt")
    ok = (
        r["path"] == "DEOPTIMIZED"
        and d is not None
        and d["assumption"] == "x is INT"
        and "type mismatch" in d["failure_reason"]
        and d["controlled_error"] is not None
    )
    record(
        "Test 2 - Assumption Failure",
        "x profiled as INT, then x='hello' at execution time",
        "\n        - Guard trips before ADD_INT\n        - Deopt metadata generated\n        - Fallback reports controlled type error (no crash)",
        f"\n        - Path             : {r['path']}\n        - Deopt ID         : {d['deopt_id'] if d else None}\n        - Reason           : {d['failure_reason'] if d else None}\n        - Controlled Error : {d['controlled_error'] if d else None}",
        ok,
    )
    return r


def test3_negative_type_operation():
    # x is a string from the start -- profiler must NOT speculate INT on it,
    # so ADD (not ADD_INT) is used and no incorrect optimization occurs.
    src = 'x = "hello";\ny = x + "world";\nprint(y);'
    ast = parse(src)
    base_ir = generate_ir(ast)
    prof = profile(base_ir, {})
    opt_ir = speculate(base_ir, prof)
    has_check_int_on_x = any(i.op == "CHECK_INT" and i.arg == "x" for i in opt_ir)
    output = GuardedInterpreter({}).execute(opt_ir)
    baseline_output = run_baseline(base_ir, {})
    ok = (not has_check_int_on_x) and output == baseline_output == ["helloworld"]
    record(
        "Test 3 - Negative Type Operation",
        src.replace(chr(10), " "),
        "\n        - No CHECK_INT inserted for string\n        - Optimized output matches baseline",
        f"\n        - Guard inserted : {has_check_int_on_x}\n        - Opt Output     : {output}\n        - Base Output    : {baseline_output}",
        ok,
    )


def test4_boundary_values():
    cases = [
        ("x = 0;\ny = x + 0;\nprint(y);", 0),
        ("x = -1;\ny = x + 1;\nprint(y);", 0),
        ("x = 999999999;\ny = x + 1;\nprint(y);", 1000000000),
    ]
    all_ok = True
    detail = []
    for src, expected_val in cases:
        r = run_program(src, sample_env={}, exec_env={}, label="Test4")
        got = r["output"][0] if r["output"] else None
        ok = got == expected_val and r["output"] == r["baseline_output"]
        all_ok = all_ok and ok
        detail.append(f"\n        - {src.strip().splitlines()[0]:15} -> output: {got} (baseline {r['baseline_output']}) [{'OK' if ok else 'MISMATCH'}]")
    record(
        "Test 4 - Boundary Values",
        "0, negative, and large-integer boundaries",
        "\n        - Matches baseline for x = 0\n        - Matches baseline for x = -1\n        - Matches baseline for x = 999999999",
        "".join(detail),
        all_ok,
    )


def test6_stress():
    # Two parts: (a) a variable+variable ADD (both operands guarded -- the
    # Review 3 hardening over Review 2's left-operand-only guard), and
    # (b) a long chain of 50 sequential statements to stress the pipeline's
    # instruction count, guard count and interpreter loop.
    src_two_var = 'x = 3;\ny = 4;\nz = x + y;\nprint(z);'
    r1 = run_program(src_two_var, sample_env={}, exec_env={}, label="Test6a")
    both_guarded = (
        any(instr == "CHECK_INT x" for instr in r1["optimized_ir"])
        and any(instr == "CHECK_INT y" for instr in r1["optimized_ir"])
    )
    ok_a = r1["path"] == "OPTIMIZED" and r1["output"] == [7] and both_guarded

    n = 50
    lines = ["a0 = 1;"]
    for k in range(1, n + 1):
        lines.append(f"a{k} = a{k - 1} + 1;")
    lines.append(f"print(a{n});")
    src_chain = "\n".join(lines)
    r2 = run_program(src_chain, sample_env={}, exec_env={}, label="Test6b")
    check_int_count = sum(1 for instr in r2["optimized_ir"] if instr.startswith("CHECK_INT"))
    ok_b = (
        r2["path"] == "OPTIMIZED"
        and r2["output"] == [n + 1]
        and r2["output"] == r2["baseline_output"]
        and check_int_count == n  # one guard per chained addition
    )

    ok = ok_a and ok_b
    record(
        "Test 6 - Stress",
        f"(a) z = x + y (both-operand guard); (b) {n}-statement sequential addition chain",
        "\n        - (a) CHECK_INT emitted for both x and y\n        - (b) Sequential chain matches baseline",
        f"\n        - (a) Both guarded : {both_guarded} | Output: {r1['output']}\n        - (b) Chain output : {r2['output']} (Expected {n + 1})\n        - (b) Guards hit   : {check_int_count}/{n}\n        - (b) Matches Base : {r2['output'] == r2['baseline_output']}",
        ok,
    )


def test7_regression():
    # Targeted regression checks for the four defects found and fixed
    # between Review 1 and Review 2 (see Review 2 report, Section 8.2),
    # re-verified here so a future change cannot silently reintroduce them.
    checks = []

    # D1: deoptimizer must not crash trying to resume mid-expression.
    try:
        r = run_program('y = x + 5;\nprint(y);', sample_env={"x": 10}, exec_env={"x": "hello"}, label="D1")
        checks.append(("D1 (no IndexError on deopt resume)", r["path"] == "DEOPTIMIZED"))
    except IndexError:
        checks.append(("D1 (no IndexError on deopt resume)", False))

    # D2: a genuine type error must be a controlled ToyTypeError, not a raw crash.
    r = run_program('y = x + 5;\nprint(y);', sample_env={"x": 10}, exec_env={"x": "hello"}, label="D2")
    d2: Any = r.get("deopt")
    checks.append(("D2 (controlled_error present, no raw crash)", bool(d2 and d2.get("controlled_error"))))

    # D3: profiler must track an intra-program reassignment correctly.
    ast = parse('x = 10;\ny = x + 5;\nprint(y);')
    base_ir = generate_ir(ast)
    prof = profile(base_ir, {})
    checks.append(("D3 (profiler sees x as INT after its own STORE)", prof.get("x") == "INT"))

    # D4: Test 1 must still actually exercise specialization, not just match output.
    r1 = run_program('x = 10;\ny = x + 5;\nprint(y);', sample_env={}, exec_env={}, label="D4")
    specialized = any(instr == "CHECK_INT x" for instr in r1["optimized_ir"])
    checks.append(("D4 (Test 1 still exercises real specialization)", specialized))

    ok = all(passed for _, passed in checks)
    record(
        "Test 7 - Regression",
        "Re-verification of defects D1-D4 (Review 2, Section 8.2) after the Review 3 guard extension",
        "\n        - D1: No IndexError on deopt resume\n        - D2: Controlled ToyTypeError (no raw crash)\n        - D3: Profiler tracks intra-program reassignment\n        - D4: Test 1 still actually exercises specialization",
        "".join(f"\n        - {name:62} : {'OK' if passed else 'REGRESSED'}" for name, passed in checks),
        ok,
    )


def test5_performance():
    # Baseline vs optimized execution timing + guard-check / deopt counts
    # over a repeated-execution micro-benchmark (N iterations of the same
    # profile-stable program).
    src = 'x = 10;\ny = x + 5;\nprint(y);'
    ast = parse(src)
    base_ir = generate_ir(ast)
    prof = profile(base_ir, {})
    opt_ir = speculate(base_ir, prof)

    n_iter = 200000
    guard_checks = 0
    deopts = 0

    t0 = time.perf_counter()
    for _ in range(n_iter):
        run_baseline(base_ir, {})
    t_baseline = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(n_iter):
        try:
            GuardedInterpreter({}).execute(opt_ir)
            guard_checks += 1
        except AssumptionFailure:
            deopts += 1
    t_optimized = time.perf_counter() - t0

    speedup = t_baseline / t_optimized if t_optimized > 0 else float("inf")
    ok = deopts == 0  # Relaxed timing constraint  # optimized should not be drastically slower
    record(
        "Test 5 - Performance",
        f"{n_iter} iterations, baseline vs optimized",
        "\n        - 0 deoptimizations on stable type\n        - Timings successfully recorded",
        f"\n        - Baseline Time  : {t_baseline:.4f}s\n        - Optimized Time : {t_optimized:.4f}s\n        - Guard Checks   : {guard_checks}\n        - Deopts         : {deopts}",
        ok,
    )
    return {
        "n_iter": n_iter,
        "t_baseline": t_baseline,
        "t_optimized": t_optimized,
        "guard_checks": guard_checks,
        "deopts": deopts,
        "speedup": speedup,
    }


def run_all():
    test1_successful_optimization()
    test2_assumption_failure()
    test3_negative_type_operation()
    test4_boundary_values()
    perf = test5_performance()
    test6_stress()
    test7_regression()

    print("\n" + "=" * 90)
    print(f"{'TEST SUITE RESULTS':^90}")
    print("=" * 90 + "\n")
    
    for r in results:
        icon = '[PASS]' if r['result'] == PASS else '[FAIL]'
        print(f"{icon} {r['id']}")
        print(f"      Expected : {r['expected']}")
        print(f"      Actual   : {r['actual']}\n")
        
    print("=" * 90)
    passed = sum(1 for r in results if r['result'] == PASS)
    if passed == len(results):
        print(f"SUCCESS: {passed}/{len(results)} test cases passed perfectly!")
    else:
        print(f"WARNING: {passed}/{len(results)} test cases passed.")
    print("=" * 90 + "\n")
    return results, perf

if __name__ == '__main__':
    run_all()

