"""
pipeline.py
Integration owner: GUNJAL SAI SANJAY (24BCT0064) -- Prototype / Baseline / Integration
Part of: BCSE307P - A31 - Speculative Optimizer with Deoptimization Support

End-to-end wiring: source -> tokens -> AST -> baseline IR -> (profile ->
speculative IR -> guarded execution -> [deoptimize if needed]).
This is the module that demonstrates module-to-module integration for
Review 2 Component 3 (Integration and Functional Prototype).
"""

from src.parser import parse
from src.ir import generate_ir, run_baseline, ToyTypeError
from src.optimizer import profile, speculate, GuardedInterpreter, Deoptimizer, AssumptionFailure


# ROLE: Coordinates the full end-to-end pipeline: parse -> baseline IR -> profile -> speculate -> guarded exec -> deopt fallback.
def run_program(source: str, sample_env: dict, exec_env: dict, label: str = ""):
    """
    Runs one toy-language program through the full speculative pipeline.

    sample_env : env used purely for profiling (Step 6, "observed behaviour")
    exec_env   : the *actual* starting environment used for the real/optimized run
                 (lets Test 2 / Test 3 inject a later type change deliberately)

    Returns a result dict describing every stage, suitable for direct
    inclusion in the Review 2 & Review 3 test-case table.
    """
    result = {"label": label, "source": source.strip()}

    ast = parse(source)
    baseline_ir = generate_ir(ast)
    result["baseline_ir"] = [str(i) for i in baseline_ir]

    type_profile = profile(baseline_ir, sample_env)
    result["type_profile"] = type_profile

    optimized_ir = speculate(baseline_ir, type_profile)
    result["optimized_ir"] = [str(i) for i in optimized_ir]

    guarded = GuardedInterpreter(exec_env)
    try:
        output = guarded.execute(optimized_ir)
        result["path"] = "OPTIMIZED"
        result["output"] = output
        result["deopt"] = None
    except AssumptionFailure as fail:
        deoptimizer = Deoptimizer()
        metadata, output = deoptimizer.deoptimize(
            deopt_id=f"D{len(deoptimizer.log):03d}",
            optimized_ir=optimized_ir,
            baseline_ir=baseline_ir,
            guard_env=guarded.env,
            failure=fail,
        )
        result["path"] = "DEOPTIMIZED"
        result["output"] = output
        result["deopt"] = metadata

    # Baseline (ground-truth) run for correctness comparison. A ToyTypeError
    # here means the *program itself* is invalid for this input (e.g. adding
    # a string to an int) -- baseline and optimized paths must agree on that.
    try:
        result["baseline_output"] = run_baseline(baseline_ir, dict(exec_env))
        result["baseline_error"] = None
    except ToyTypeError as e:
        result["baseline_output"] = None
        result["baseline_error"] = str(e)
    return result


if __name__ == "__main__":
    r = run_program(
        'x = 10;\ny = x + 5;\nprint(y);',
        sample_env={}, exec_env={}, label="Demo"
    )
    print(r["path"], r["output"], "baseline:", r["baseline_output"])
