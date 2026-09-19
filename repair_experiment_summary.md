# MathRepair Repair Experiment Summary

Model: `qwen2-math:1.5b` | Runs: 36 | Problems: 12 | Samples/problem: 3

## Strategy Comparison

| Strategy | Answer accuracy | Valid traces | Model calls | Tokens |
|---|---:|---:|---:|---:|
| no_repair | 86.1% (31/36) | 80.6% (29/36) | 36 | 22,469 |
| symbolic_oracle_repair | 100.0% (36/36) | 100.0% (36/36) | 36 | 22,469 |
| verified_model_repair | 100.0% (36/36) | 97.2% (35/36) | 44 | 28,269 |

## Repair Metrics

| Metric | Value |
|---|---:|
| Detected error runs | 7 |
| Accepted model repairs | 6/7 (85.7%) |
| Wrong-answer recovery | 5/5 (100.0%) |
| Answer regressions | 0 |
| Average candidate calls/error | 1.14 |

## Compute Efficiency

| Metric | Value |
|---|---:|
| Repair total-token overhead | 25.8% |
| Repair call overhead | 22.2% |
| Repair total tokens/corrected wrong answer | 1160.0 |
| Answer accuracy gain | 13.9 pp |
| Trace-validity gain | 16.7 pp |

## Results By Error Type

| Error type | Detected | Accepted repair | Corrected wrong |
|---|---:|---:|---:|
| algebraic_transformation_error | 5 | 5 | 4 |
| arithmetic_error | 1 | 1 | 1 |
| sign_error | 1 | 0 | 0 |

## Results By Category

| Category | Runs | Answer before | Answer after | Trace before | Trace after |
|---|---:|---:|---:|---:|---:|
| cubic_factorization | 3 | 3/3 | 3/3 | 3/3 | 3/3 |
| cubic_transformation | 3 | 3/3 | 3/3 | 3/3 | 3/3 |
| large_coefficients | 6 | 6/6 | 6/6 | 6/6 | 6/6 |
| large_fractions | 6 | 4/6 | 6/6 | 4/6 | 6/6 |
| nested_distribution | 3 | 0/3 | 3/3 | 0/3 | 3/3 |
| nested_subtraction | 3 | 3/3 | 3/3 | 2/3 | 2/3 |
| rational_equation | 6 | 6/6 | 6/6 | 5/6 | 6/6 |
| repeated_cubic_root | 3 | 3/3 | 3/3 | 3/3 | 3/3 |
| repeated_quadratic_root | 3 | 3/3 | 3/3 | 3/3 | 3/3 |

## Matched-Budget Comparison

Budget rule: Per error run, global prompt plus completion tokens may not exceed the prompt plus completion tokens used by local model repair.

| Strategy | Answer accuracy | Valid traces | Extra calls | Extra tokens |
|---|---:|---:|---:|---:|
| no_repair | 86.1% | 80.6% | 0 | 0 |
| verified_global_regeneration | 88.9% | 88.9% | 9 | 4,841 |
| verified_local_repair | 100.0% | 97.2% | 8 | 5,800 |

Global budget utilization: 83.5%

## Caveats

- This is a small 12-problem stress set, not a benchmark result.
- Symbolic oracle repair uses verifier-derived correct states.
- Symbolic tool runtime is not converted into token cost.
- Ollama GPU sampling may vary slightly even with recorded seeds.
