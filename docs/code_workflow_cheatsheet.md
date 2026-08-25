# Code Workflow & Module Architecture Cheatsheet
**Course**: BCSE307P - Compiler Design | **Review 3**  
**Project**: Speculative Optimizer with On-Stack Deoptimization Support

---

## 🔄 End-to-End Execution Workflow Diagram

```text
[ Source Code Text ]  (e.g., "x = 10; y = x + 5; print(y);")
       │
       ▼
[ src/lexer.py ] ─────▶ tokenize() ──────▶ [ Token Stream ] (Token(ID, 'x'), Token(ASSIGN, '='), ...)
       │
       ▼
[ src/parser.py ] ────▶ parse() ─────────▶ [ Abstract Syntax Tree (AST) ] (Program, Assign, BinOp, Print)
       │
       ▼
[ src/ir.py ] ────────▶ generate_ir() ───▶ [ Baseline IR ] (LOAD_CONST, STORE, LOAD, ADD, PRINT)
       │
       ▼
[ src/optimizer.py ] ─▶ profile() ───────▶ [ Type Profile ] ({'x': 'INT', 'y': 'INT'})
       │
       ▼
[ src/optimizer.py ] ─▶ speculate() ─────▶ [ Speculative IR ] (Adds CHECK_INT x, replaces ADD with ADD_INT)
       │
       ▼
[ src/optimizer.py ] ─▶ GuardedInterpreter.execute()
       │
       ├─────────────────────────────────────────┐
       │ (Assumptions Hold)                      │ (Guard Check Fails: CHECK_INT trips)
       ▼                                         ▼
[ Fast Optimized Execution ]             [ AssumptionFailure Raised ]
       │                                         │
       │                                         ▼
       │                                 [ src/optimizer.py: Deoptimizer.deoptimize() ]
       │                                         │
       │                                         ├─▶ Capture metadata & current environment
       │                                         ├─▶ Map failed IP back to baseline statement
       │                                         └─▶ Resume execution via BaselineInterpreterSimple
       ▼                                         ▼
[ Return Fast Result ]                   [ Return Rescued Output / Controlled Error ]
```

---

## 📁 File-by-File Detailed Responsibilities

### 1. `src/lexer.py` (Frontend Tokenizer)
- **Primary Function**: `tokenize(source: str)`
- **Input**: Raw source code string (e.g. `'x = 10;\ny = x + 5;\nprint(y);'`).
- **Processing**: Matches regex patterns in `TOKEN_SPEC` (`SKIP`, `NUMBER`, `STRING`, `ID`, `ASSIGN`, `PLUS`, etc.).
- **Output**: List of `Token` objects ending with an `EOF` token.

---

### 2. `src/parser.py` (Frontend Syntactic Analyzer)
- **Primary Function**: `parse(source: str) -> Program`
- **Input**: Token list from `tokenize()`.
- **Processing**: Recursive-descent grammar parsing:
  - `parse_program()` -> sequence of statements
  - `parse_statement()` -> `Assign` or `Print`
  - `parse_expression()` -> handles `+` additions with left-associativity
  - `parse_term()` -> handles integer literals, strings, and variable lookups
- **Output**: Root `Program` AST node containing a list of statement nodes (`Assign`, `Print`, `BinOp`, `Literal`, `Var`).

---

### 3. `src/ir.py` (Intermediate Representation & Baseline VM)
- **Primary Function**: `generate_ir(program: Program) -> list[Instr]`
- **Input**: AST `Program` node.
- **Processing**: Post-order traversal flattening expressions into a linear stack-machine instruction stream.
- **Output**: List of baseline `Instr` objects (`LOAD_CONST`, `STORE`, `LOAD`, `ADD`, `PRINT`).
- **Baseline VM**: `BaselineInterpreterSimple(env)` executes baseline IR using an operand stack and variable map, performing dynamic type checking via `toy_add()`.

---

### 4. `src/optimizer.py` (Speculative Optimization & Deoptimizer)
- **Components**:
  1. `profile(ir, sample_env)`: Simulates execution over sample inputs, tracking variable types feeding into `ADD`. Returns `{var_name: 'INT' | 'STRING' | 'MIXED'}`.
  2. `speculate(ir, type_profile)`: Inspects operand types for both left and right variables (Review 3 hardening). If both are INT, inserts `CHECK_INT` guards and emits specialized `ADD_INT`.
  3. `GuardedInterpreter(env)`: High-performance VM executing speculative IR. Raises `AssumptionFailure` the moment a `CHECK_INT` guard fails.
  4. `Deoptimizer`: On failure, builds failure metadata, maps the failing instruction index back to the baseline statement, reconstructs the variable environment, and resumes execution in `BaselineInterpreterSimple`.

---

### 5. `src/pipeline.py` (End-to-End Orchestrator)
- **Primary Function**: `run_program(source, sample_env, exec_env, label)`
- **Input**: Source code string, profiling sample environment, and actual execution environment.
- **Processing**: Calls `parse` -> `generate_ir` -> `profile` -> `speculate` -> `GuardedInterpreter.execute()`. On `AssumptionFailure`, delegates to `Deoptimizer.deoptimize()`. Also runs `run_baseline` for ground-truth comparison.
- **Output**: Result dictionary with full pipeline trace (`baseline_ir`, `type_profile`, `optimized_ir`, `path`, `output`, `deopt`).

---

### 6. `src/comparison_engine.py` & `compare.py` (Comparative Benchmark Suite)
- **Primary Function**: `run_comparative_demonstration()`
- **Compares**:
  - Baseline execution (dynamic dispatch overhead).
  - Speculation without deoptimization (fatal crash on type mutation).
  - Speculation with deoptimization (safe recovery, high throughput).
  - Degraded throughput / thrashing analysis (overhead of frequent deopts).
