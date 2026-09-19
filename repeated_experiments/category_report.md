# MathRepair Category Analysis

Problem set: `stress_model_problems.csv` | Trials: 5

Values are mean answer accuracy and valid-trace rate across seeds.

| Category | Runs/trial | No repair | Global regeneration | Local repair |
|---|---:|---:|---:|---:|
| cubic_factorization | 3 | 93.3% +/- 14.9% [74.8%, 100.0%] answer; 86.7% +/- 29.8% [49.7%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace |
| cubic_transformation | 3 | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace |
| large_coefficients | 6 | 96.7% +/- 7.5% [87.4%, 100.0%] answer; 96.7% +/- 7.5% [87.4%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace | 96.7% +/- 7.5% [87.4%, 100.0%] answer; 96.7% +/- 7.5% [87.4%, 100.0%] trace |
| large_fractions | 6 | 66.7% +/- 11.8% [52.0%, 81.3%] answer; 66.7% +/- 11.8% [52.0%, 81.3%] trace | 86.7% +/- 7.5% [77.4%, 95.9%] answer; 86.7% +/- 7.5% [77.4%, 95.9%] trace | 93.3% +/- 9.1% [82.0%, 100.0%] answer; 86.7% +/- 13.9% [69.4%, 100.0%] trace |
| nested_distribution | 3 | 0.0% +/- 0.0% [0.0%, 0.0%] answer; 0.0% +/- 0.0% [0.0%, 0.0%] trace | 0.0% +/- 0.0% [0.0%, 0.0%] answer; 0.0% +/- 0.0% [0.0%, 0.0%] trace | 93.3% +/- 14.9% [74.8%, 100.0%] answer; 73.3% +/- 43.5% [19.4%, 100.0%] trace |
| nested_subtraction | 3 | 93.3% +/- 14.9% [74.8%, 100.0%] answer; 86.7% +/- 18.3% [64.0%, 100.0%] trace | 93.3% +/- 14.9% [74.8%, 100.0%] answer; 93.3% +/- 14.9% [74.8%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 93.3% +/- 14.9% [74.8%, 100.0%] trace |
| rational_equation | 6 | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 96.7% +/- 7.5% [87.4%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 96.7% +/- 7.5% [87.4%, 100.0%] trace |
| repeated_cubic_root | 3 | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace |
| repeated_quadratic_root | 3 | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace |

Interpretation: values summarize seed variation; they are not problem-sampling confidence intervals.
