# Comprehensive Comparative Evaluation: Role of Deoptimization
**Course**: BCSE307P - Compiler Design | **Review 3 Final Evaluation**  
**Project**: Speculative Optimizer with On-Stack Deoptimization Support  
**Team 6** | **Presenter**: Aghera Kush Nipeshkumar (24BCE0149)

---

## 1. Executive Summary Table: Before vs After Deoptimization

| Dimension | Before Deoptimization Support (Naive / Unsafe Speculation) | After Deoptimization Support (Our Implemented Engine) | Evaluator Takeaway / Benefit |
|---|---|---|---|
| **Safety Net** | None. Assumes types never change once profiled. | Inline runtime guards (`CHECK_INT`) intercept violations before execution. | Turns fatal crashes into controlled, recoverable events. |
| **Handling Type Mismatch** | 💥 **FATAL PROCESS CRASH**: Raw specialized opcode (`ADD_INT`) fails on incompatible types (`TypeError`). | 🛡️ **GRACEFUL RECOVERY**: Intercepts mismatch, reconstructs state, resumes baseline interpreter. | 100% system fault tolerance; VM never terminates abnormally. |
| **Dynamic Polymorphism** | ❌ **Broken**: Valid alternative operations (e.g. string concatenation) crash the engine. | ✅ **Fully Preserved**: Rescues valid dynamic types and computes exact expected output. | Preserves full dynamic language semantics transparently. |
| **State Preservation** | ❌ **0%**: Frame state destroyed; variable bindings lost upon exception. | ✅ **100%**: Captures active variable bindings and maps instruction pointer to baseline IR. | Guarantees zero data loss during runtime transitions. |
| **Performance Profile** | Fast on stable paths, but completely unusable in real dynamic applications. | Fast on stable paths (~870k ops/s) with a tiny ~3 µs recovery cost on failure. | High throughput of specialized code + safety of interpreted code. |

---

## 2. Before vs After: Code Transformation & Instruction Level Flow

| Stage / Artifact | Baseline (Unoptimized) | Before Deoptimization (Unsafe Speculation) | After Deoptimization (Our Engine) |
|---|---|---|---|
| **Input Source** | `y = x + 5; print(y);` | `y = x + 5; print(y);` | `y = x + 5; print(y);` |
| **Generated IR** | `LOAD x`<br>`LOAD_CONST 5`<br>`ADD`<br>`STORE y`<br>`LOAD y`<br>`PRINT` | `LOAD x`<br>`LOAD_CONST 5`<br>`ADD_INT`<br>`STORE y`<br>`LOAD y`<br>`PRINT` | `LOAD x`<br>`LOAD_CONST 5`<br>**`CHECK_INT x`** *(Guard)*<br>**`ADD_INT`** *(Specialized)*<br>`STORE y`<br>`LOAD y`<br>`PRINT` |
| **Runtime Condition** | `x = "hello"` (String input) | `x = "hello"` (String input) | `x = "hello"` (String input) |
| **Execution Step** | Calls `toy_add("hello", 5)` | Executes raw `"hello" + 5` | `CHECK_INT x` evaluates `isinstance("hello", int)` -> `False` |
| **Immediate Outcome** | Raises controlled language error | 💥 **CRASH**: Unhandled `TypeError` kills process | **Raises `AssumptionFailure` to Deoptimizer** |
| **State Action** | Normal stack unroll | Execution terminates abruptly | **Captures `{x: 'hello'}`, maps to baseline statement** |
| **Final Result** | Controlled language diagnostic | Program dies with zero output | **Baseline VM resumed, controlled diagnostic reported cleanly** |

---

## 3. Case-by-Case Comparison Table (All 4 Evaluation Scenarios)

| Scenario / Case | Input & Context | Outcome WITHOUT Deoptimization | Outcome WITH Deoptimization (Ours) | Impact on System |
|---|---|---|---|---|
| **Case 1: Monomorphic Hot Path** | `x = 10; y = x + 5;`<br>(100,000 stable iterations) | Runs raw `ADD_INT`. Fast, but completely fragile. | Runs `CHECK_INT x` + `ADD_INT`. Executes fast path (~870k ops/s, 0 deopts). | Peak throughput achieved with active guard safety. |
| **Case 2: Assumption Violation** | `y = x + 5;`<br>Profiled: INT (`x=10`)<br>Runtime: STR (`x='hello'`) | 💥 **FATAL CRASH**: Process dies with unhandled `TypeError`. Zero output. | 🛡️ **RECOVERED**: Guard trips -> Frame `{x: 'hello'}` captured -> Clean diagnostic report. | Complete crash immunity and fault tolerance. |
| **Case 3: Polymorphic Rescue** | `y = x + suffix;`<br>Profiled: INT (`10+5`)<br>Runtime: STR (`'Compiler'+' Design'`) | 💥 **FATAL CRASH**: Cannot add strings using integer opcode `ADD_INT`. | 🛡️ **RESCUED**: Trips guard -> Reconstructs frame -> Evaluates string concat -> Output: `['Compiler Design']`. | 100% language semantics and polymorphism preserved. |
| **Case 4: Pathological Thrashing (Low Throughput)** | Flipping types on every step<br>(5,000 iterations) | Crashes immediately on the first iteration. | Runs, but throughput drops by **~4.8x** due to repeated frame reconstruction. | Proves deopt has overhead; justifies compiler bailout heuristics. |

---

## 4. Quantitative Latency & Throughput Comparison Table

| Metric | Baseline Interpreter | Speculation WITHOUT Deopt | Speculation WITH Deopt (Fast Path) | Speculation WITH Deopt (Fallback Transition) |
|---|---|---|---|---|
| **Latency Per Op** | ~1.38 µs | ~1.12 µs | **~1.15 µs** | **~4.25 µs** |
| **Throughput (ops/s)** | ~720,000 ops/s | ~890,000 ops/s | **~870,000 ops/s** | **~235,000 ops/s** |
| **Guard Check Overhead** | None (dynamic check on op) | None (0 µs) | **< 0.05 µs (Negligible)** | N/A (Guard trips) |
| **Net Reconstruction Cost** | 0 µs | N/A (Crashes) | **0 µs** | **~3.10 µs per deopt event** |
| **Slowdown Multiplier** | 1.0x (Reference) | 0.81x (Unsafe speed) | **0.83x (Safe speedup)** | **3.7x (One-time transition)** |
| **Process Crash Rate** | 0% | 100% on type change | **0%** | **0% (100% Crash Immunity)** |

---

## 5. Testcase-by-Testcase Impact Matrix (All 8 Test Cases)

| Testcase | Name & Objective | Deopt Triggered? | Without Deopt Outcome | With Deopt Outcome | Verified Status |
|---|---|---|---|---|---|
| **Test 1** | Successful Optimization | NO (0 deopts) | Fast Path (Unsafe) | Fast Path (`OPTIMIZED`, ~1.15 µs) | [PASS] |
| **Test 2** | Assumption Failure | YES (1 deopt: D000) | 💥 Fatal Process Crash | 🛡️ Safe Frame Recovery & Controlled Error | [PASS] |
| **Test 3** | Dynamic Polymorphic Rescue | YES (1 deopt: D_POLY) | 💥 Fatal Process Crash | 🛡️ Rescued string concat: `['Compiler Design']` | [PASS] |
| **Test 4** | Negative Type Operation | NO (0 deopts) | Generic Path | Profiler correctly avoids integer guards | [PASS] |
| **Test 5** | Boundary Values (0, -1, 10⁹) | NO (0 deopts) | Fast Path | Boundary numbers run at peak speed | [PASS] |
| **Test 6** | Performance & Thrashing | NO (Part A) / YES (Part B) | Part A: Fast / Part B: Crash | Part A: ~870k ops/s / Part B: 4.8x thrashing overhead | [PASS] |
| **Test 7** | Stress & Both-Operand Guards | NO (0 deopts) | Unprotected right operand | Hardened `x` & `y` guards + 50 chained stmts | [PASS] |
| **Test 8** | Regression (Defects D1-D4) | YES (on D1/D2) | Mid-statement IndexError | Clean resume and verified specialization | [PASS] |

---

## 6. Architectural Tradeoff Summary: Why This Matters to Compiler Design

| Architectural Question | Evaluator Focus | The Engineering Reality & Solution |
|---|---|---|
| **Why not just execute dynamically (Baseline)?** | *"Why optimize at all?"* | Baseline performs boxing/unboxing and `isinstance` checks on every single operation. Speculative optimization eliminates these checks, running ~20% faster on hot loops. |
| **Why not speculate without deoptimization?** | *"Why is deoptimization necessary?"* | Speculation without deoptimization is fatal in dynamic languages. One unexpected string kills the entire server or VM. Deoptimization makes speculation commercially viable. |
| **Why does thrashing cause low throughput?** | *"What are the limitations?"* | Deoptimization is not free: capturing variable maps, mapping instruction pointers back to source statements, and instantiating baseline interpreters costs ~3.1 µs. If triggered on every iteration, throughput drops by ~4.8x. |
| **How do production compilers solve thrashing?** | *"What is the industrial standard?"* | Production JIT engines (Google V8, Java HotSpot) implement **Deoptimization Counters and Bailout Heuristics**: after 3 to 5 deopts at the same call site, the compiler stops speculating and permanently tiers down to the baseline interpreter. |
