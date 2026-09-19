# MathRepair Model Comparison

Baseline: `qwen2-math:1.5b`
Candidate: `qwen2-math:7b`
Problem set: `expanded_heldout_model_problems.csv` (36 problems)
Temperature: `1.4` | Samples/problem: `1`
Generation failures: baseline `0` | candidate `10`

Positive values mean the candidate model improved over the baseline.

| Strategy | Answer accuracy difference | Trace-validity difference |
|---|---:|---:|
| no_repair | -15.7 pp | -12.0 pp |
| verified_global_regeneration | -16.7 pp | -15.7 pp |
| verified_local_repair | -14.8 pp | -13.9 pp |

The paired local-minus-global intervals for each model remain in the source aggregate reports; this table compares model means.
