# Speculative Optimizer with On-Stack Deoptimization Support

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Course](https://img.shields.io/badge/Course-BCSE307P%20Compiler%20Design-green.svg)](https://vit.ac.in)
[![Review](https://img.shields.io/badge/Status-Review%203%20Final-success.svg)]()
[![Tests](https://img.shields.io/badge/Tests-7%2F7%20Passing-brightgreen.svg)]()

> **BCSE307P - Compiler Design Project (Review 3 Final)**  
> **Team 6 | Vellore Institute of Technology, Vellore**

---

## 👥 Team Members

| Name | Registration No. | Module Owned |
|---|---|---|
| **Gunjal Sai Sanjay** | 24BCT0064 | Baseline IR, Interpreter & Pipeline Integration |
| **Aghera Kush Nipeshkumar** | 24BCE0149 | Problem Analysis, Test Suite, QA & Comparative Study |
| **Piyush Mundhra** | 24BCE2173 | Lexer & Recursive-Descent Parser (Frontend) |
| **C Vishwajeet Kumar** | 24BCE0341 | Type Profiler, Speculative Optimizer & Deoptimizer |

---

## 📖 Project Overview

Dynamic programming languages (e.g., Python, JavaScript) suffer from persistent runtime type-dispatch overhead on every primitive operation. This project designs and implements an **interpreter-level speculative optimizer with on-stack deoptimization support**, emulating modern dynamic JIT architectures (such as Google V8, Java HotSpot, and PyPy):

1. **Type Profiling**: Analyzes runtime variables across sample executions to infer stable primitive types.
2. **Speculative Specialization**: Optimistically replaces generic, polymorphic operations (`ADD`) with unboxed, specialized arithmetic opcodes (`ADD_INT`).
3. **Runtime Guards**: Inserts lightweight inline checks (`CHECK_INT`) to ensure type assumptions hold before specialized opcodes run.
4. **On-Stack Deoptimization**: If an assumption is violated (e.g., a string or polymorphic type arrives unexpectedly), the deoptimizer captures variable bindings, maps the instruction pointer back to the baseline statement, and seamlessly transfers execution to the baseline interpreter without crashing the virtual machine.

---

## 🏗️ Compiler Architecture & Workflow

```text
  [ Source Code ]  (e.g., "x = 10; y = x + 5; print(y);")
         │
         ▼
  [ src/lexer.py ] ─────▶ tokenize() ──────▶ [ Token Stream ]
         │
         ▼
  [ src/parser.py ] ────▶ parse() ─────────▶ [ Abstract Syntax Tree (AST) ]
         │
         ▼
  [ src/ir.py ] ────────▶ generate_ir() ───▶ [ Baseline IR ] (LOAD, STORE, ADD, PRINT)
         │
         ▼
  [ src/optimizer.py ] ─▶ profile() ───────▶ [ Type Profile ] ({'x': 'INT'})
         │
         ▼
  [ src/optimizer.py ] ─▶ speculate() ─────▶ [ Speculative IR ] (CHECK_INT x, ADD_INT)
         │
         ▼
  [ Guarded Execution ]
         │
         ├─────────────────────────────────────────┐
         │ (Assumption Holds)                      │ (Guard Check Fails: CHECK_INT trips)
         ▼                                         ▼
  [ Fast Path Execution ]                   [ AssumptionFailure Raised ]
  - High Throughput (~850k ops/s)                  │
  - Direct specialized ADD_INT                     ▼
                                            [ src/optimizer.py: Deoptimizer ]
                                            - Captures current variable bindings
                                            - Maps instruction pointer back to baseline
                                            - Re-enters BaselineInterpreterSimple
                                                   │
                                                   ▼
                                            [ Graceful Recovery (Zero Crash) ]
```

---

## 📁 Repository Structure

```text
├── main.py                     # Master execution runner (runs all stages one by one)
├── presentation_helper.md      # Presenter guide & viva explanation cheat sheet
├── README.md                   # Project documentation
├── .gitignore                  # Git cache ignore rules
├── src/
│   ├── lexer.py                # Tokenizer (Lexical Analysis)
│   ├── parser.py               # Recursive-descent parser (AST Construction)
│   ├── ir.py                   # Intermediate representation & baseline stack VM
│   ├── optimizer.py            # Profiler, speculative optimizer, runtime guards & deoptimizer
│   ├── pipeline.py             # End-to-end integration orchestrator
│   └── comparison_engine.py    # Unsafe speculative runner & benchmarking suite
├── tests/
│   └── suite.py                # Formal 7-test test suite
└── docs/
    ├── code_workflow_cheatsheet.md       # Pipeline diagrams and input/output mapping
    └── review3_evaluation_cheatsheet.md  # Viva questions and answers for evaluators
```

---

## Quick Start & Execution

Run the master script to execute all verification and benchmark test cases sequentially:

```bash
python main.py
```

### What `main.py` Executes (One by One)
Each test case executes with clean single-line separation:
1. **[TEST 1] Successful Optimization**: Monomorphic fast path, specialized `ADD_INT` emitted, 1.4 µs latency.
2. **[TEST 2] Assumption Failure**: Type mismatch intercepted, state reconstructed, crash avoided.
3. **[TEST 3] Dynamic Polymorphic Rescue**: Resolves valid string concatenation dynamically (`'Compiler Design'`).
4. **[TEST 4] Negative Type Operation**: Profiler correctly avoids integer specialization on strings.
5. **[TEST 5] Boundary Value Stability**: Large numbers, zero, and negative values run at peak speed.
6. **[TEST 6] Performance & Low-Throughput Thrashing**: 200k stable iterations vs 5k thrashing iterations (5.0x slowdown).
7. **[TEST 7] Stress & Both-Operand Guarding**: Hardened both-operand guards & 50-statement chain.
8. **[TEST 8] Regression Verification**: Formally re-verifies defects D1 through D4.

---

## Comparative Evaluation Matrix

| Dimension / Feature | Baseline Interpreter | Unsafe Speculation (NO Deopt) | Speculative + Deoptimization (Ours) |
|---|---|---|---|
| **Execution Path** | Generic dynamic dispatch (`toy_add`) | Blind `ADD_INT` | Guarded `ADD_INT` + `CHECK_INT` |
| **Stable Path Throughput** | Moderate (~720,000 ops/s) | High (~750,000 ops/s) | High (~750,000 ops/s) |
| **Handling Type Mismatch** | Controlled Language Error | [FATAL CRASH] | [GRACEFUL RECOVERY] |
| **Dynamic Polymorphism** | Supported | Broken / Fatal Crash | 100% Supported via Fallback |
| **State Reconstruction** | N/A | None (0%) | Full Frame & Environment Restore |
| **System Reliability** | 100% | 0% (Fatal Aborts) | 100% Fault Tolerant |

---

## Quantitative Microsecond Benchmark

Measured over repeated iterations:
* **When Deopt does NOT occur (Fast Path)**: **~1.40 us per operation** (~710,000 ops/sec).
* **When Deopt DOES occur (Fallback Path)**: **~5.00 us per operation** (~200,000 ops/sec).
* **Net Cost of State Reconstruction**: **~3.60 us per deopt event**.
* **Compiler Design Insight**: Paying a one-time ~3.6 microsecond state reconstruction cost on rare polymorphic mutations grants **100% crash immunity** and preserves dynamic language semantics. When code thrashes (assumptions fail continuously), throughput drops by **~5.0x**, demonstrating why production JIT compilers (V8, HotSpot) implement **Deoptimization Counters and Bailout Policies** to permanently tier down after repeated deoptimizations.

---

## Formal Test Suite Summary

| Test ID | Test Name | Focus | Deopt? | Result |
|---|---|---|---|---|
| **Test 1** | Successful Optimization | Monomorphic fast path, `ADD_INT` emitted | NO | [PASS] |
| **Test 2** | Assumption Failure | Type mismatch caught before add, graceful recovery | YES | [PASS] |
| **Test 3** | Dynamic Polymorphic Rescue | Valid string concatenation handled via fallback | YES | [PASS] |
| **Test 4** | Negative Type Operation | Strings correctly avoid integer specialization | NO | [PASS] |
| **Test 5** | Boundary Values | Integer boundaries (0, -1, 999,999,999) | NO | [PASS] |
| **Test 6** | Performance & Thrashing | 200,000 iterations hot path & 5,000 thrashing runs | NO / YES | [PASS] |
| **Test 7** | Stress Test (Review 3) | Both-operand guarding (`z = x + y`) & 50 chained statements | NO | [PASS] |
| **Test 8** | Regression Test (Review 3) | Re-verification of defects D1 through D4 | YES | [PASS] |

---

## License
Developed as part of the BCSE307P Compiler Design curriculum at VIT Vellore.
