# Review 3 Live Presentation Cheatsheet & Terminal Guide
**Course**: BCSE307P - Compiler Design | **Team 6**  
**Presenter**: Aghera Kush Nipeshkumar (24BCE0149)  
**Project**: Speculative Optimizer with On-Stack Deoptimization Support

---

## ⚡ The ONLY Command You Need to Run
When presenting in front of mam, open your VS Code terminal in the project directory and type:

```bash
python main.py
```

It executes all 8 test cases cleanly one by one, separated by a single line.

---

## 🗣️ What to Say to Mam for Each Test Case

### [TEST 1] Successful Optimization (Monomorphic Fast Path)
* **What it shows**: Code `x = 10; y = x + 5; print(y);` running on the speculative path with `CHECK_INT` and `ADD_INT`.
* **What you say to mam**:
  > *"Test 1 demonstrates successful speculative specialization. The profiler identified `x` as an integer, so the compiler replaced generic addition with specialized `ADD_INT` guarded by `CHECK_INT x`. It executes on the fast path in 1.4 µs with 0 deoptimizations."*

---

### [TEST 2] Assumption Failure (Type Mismatch: Crash vs Recovery)
* **What it shows**: Code `y = x + 5;` where runtime input changes to string `x = 'hello'`.
* **What you say to mam**:
  > *"Test 2 proves the core value of deoptimization. Without deoptimization, raw `ADD_INT` causes a fatal unhandled `TypeError` that crashes the entire process. With our deoptimizer, the runtime guard catches the mismatch, captures the frame `{'x': 'hello'}`, and gracefully resumes baseline execution with zero crash."*

---

### [TEST 3] Dynamic Polymorphic Rescue (Valid String Addition)
* **What it shows**: Code `y = x + suffix;` profiled on integers, but receives strings (`'Compiler' + ' Design'`).
* **What you say to mam**:
  > *"Test 3 demonstrates dynamic polymorphism preservation. Without deoptimization, `ADD_INT` fails on strings. With deoptimization, the engine deoptimizes to baseline `toy_add`, correctly computes string concatenation, and outputs `'Compiler Design'`."*

---

### [TEST 4] Negative Type Operation (Strings Avoid Speculation)
* **What it shows**: Code with string concatenation from the start.
* **What you say to mam**:
  > *"Test 4 verifies profiler precision. The profiler identifies string operations early and avoids inserting false integer guards, allowing clean dynamic execution without unnecessary overhead."*

---

### [TEST 5] Boundary Value Stability
* **What it shows**: Large integers (`999999999`), zero, and negative values.
* **What you say to mam**:
  > *"Test 5 confirms numerical stability. Boundary values run at peak speculative throughput without triggering false deoptimizations."*

---

### [TEST 6] Performance & Low-Throughput Thrashing Analysis
* **What it shows**: 
  - Part A: 200,000 iterations hot path @ ~750,000 ops/sec.
  - Part B: 5,000 iterations thrashing with continuous assumption failures (5.0x slower).
* **What you say to mam**:
  > *"Mam, here is the low-throughput case you asked about. On a stable loop, we get high throughput. But in Part B, when assumptions fail on every single iteration, state reconstruction causes a 5.0x slowdown. This explains why industrial JITs like Google V8 use Deopt Bailout Heuristics to permanently tier down if code thrashes."*

---

### [TEST 7] Stress Test & Both-Operand Guarding (Review 3 Hardening)
* **What it shows**: Both operands guarded (`z = x + y` checks both `x` and `y`) and a 50-statement dependency chain.
* **What you say to mam**:
  > *"In Review 2, our guard only checked the left operand. For Review 3, we hardened the compiler to guard both operands (`x` and `y`), and verified stability over a 50-statement sequential addition chain."*

---

### [TEST 8] Regression Verification (Review 2 Defects D1 to D4)
* **What it shows**: Verification that defects D1 to D4 remain fixed.
* **What you say to mam**:
  > *"Test 8 re-verifies our four Review 2 defect fixes, proving there are no `IndexError` regressions during frame resumption and that real specialization is exercised."*

---

### SUMMARY METRICS:
* **Fast Path Latency**: ~1.40 µs per operation
* **Fallback Path Latency**: ~5.00 µs per operation (Net state reconstruction cost: ~3.60 µs)
* **System Safety**: 100% (Zero fatal crashes across all cases)
