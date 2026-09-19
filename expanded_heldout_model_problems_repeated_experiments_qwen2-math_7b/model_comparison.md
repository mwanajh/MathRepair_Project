# MathRepair Model Comparison

Baseline: `qwen2-math:1.5b`
Candidate: `qwen2-math:7b`
Problem set: `expanded_heldout_model_problems.csv` (36 problems)
Temperature: `1.4` | Samples/problem: `1`
Generation failures: baseline `0` | candidate `91`

Positive values mean the candidate model improved over the baseline.

| Strategy | Answer accuracy difference | Trace-validity difference |
|---|---:|---:|
| no_repair | -77.8 pp | -75.0 pp |
| verified_global_regeneration | -78.7 pp | -78.7 pp |
| verified_local_repair | -87.0 pp | -87.0 pp |

The paired local-minus-global intervals for each model remain in the source aggregate reports; this table compares model means.
