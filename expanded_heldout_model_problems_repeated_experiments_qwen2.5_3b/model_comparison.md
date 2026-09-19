# MathRepair Model Comparison

Baseline: `qwen2-math:1.5b`
Candidate: `qwen2.5:3b`
Problem set: `expanded_heldout_model_problems.csv` (36 problems)
Temperature: `1.4` | Samples/problem: `1`
Generation failures: baseline `0` | candidate `24`

Positive values mean the candidate model improved over the baseline.

| Strategy | Answer accuracy difference | Trace-validity difference |
|---|---:|---:|
| no_repair | -43.5 pp | -43.5 pp |
| verified_global_regeneration | -36.1 pp | -38.0 pp |
| verified_local_repair | -51.9 pp | -52.8 pp |

The paired local-minus-global intervals for each model remain in the source aggregate reports; this table compares model means.
