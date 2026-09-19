# MathRepair Category Analysis

Problem set: `expanded_heldout_model_problems.csv` | Trials: 3

Values are mean answer accuracy and valid-trace rate across seeds.

| Category | Runs/trial | No repair | Global regeneration | Local repair |
|---|---:|---:|---:|---:|
| cubic_factorization | 2 | 83.3% +/- 28.9% [11.6%, 100.0%] answer; 83.3% +/- 28.9% [11.6%, 100.0%] trace | 83.3% +/- 28.9% [11.6%, 100.0%] answer; 83.3% +/- 28.9% [11.6%, 100.0%] trace | 83.3% +/- 28.9% [11.6%, 100.0%] answer; 83.3% +/- 28.9% [11.6%, 100.0%] trace |
| cubic_transformation | 2 | 33.3% +/- 28.9% [0.0%, 100.0%] answer; 33.3% +/- 28.9% [0.0%, 100.0%] trace | 33.3% +/- 28.9% [0.0%, 100.0%] answer; 33.3% +/- 28.9% [0.0%, 100.0%] trace | 33.3% +/- 28.9% [0.0%, 100.0%] answer; 33.3% +/- 28.9% [0.0%, 100.0%] trace |
| large_coefficients | 4 | 91.7% +/- 14.4% [55.8%, 100.0%] answer; 91.7% +/- 14.4% [55.8%, 100.0%] trace | 91.7% +/- 14.4% [55.8%, 100.0%] answer; 91.7% +/- 14.4% [55.8%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace |
| large_fractions | 6 | 38.9% +/- 19.2% [0.0%, 86.7%] answer; 38.9% +/- 19.2% [0.0%, 86.7%] trace | 38.9% +/- 19.2% [0.0%, 86.7%] answer; 38.9% +/- 19.2% [0.0%, 86.7%] trace | 77.8% +/- 9.6% [53.9%, 100.0%] answer; 77.8% +/- 9.6% [53.9%, 100.0%] trace |
| nested_distribution | 4 | 66.7% +/- 14.4% [30.8%, 100.0%] answer; 66.7% +/- 14.4% [30.8%, 100.0%] trace | 75.0% +/- 0.0% [75.0%, 75.0%] answer; 75.0% +/- 0.0% [75.0%, 75.0%] trace | 91.7% +/- 14.4% [55.8%, 100.0%] answer; 91.7% +/- 14.4% [55.8%, 100.0%] trace |
| nested_subtraction | 4 | 91.7% +/- 14.4% [55.8%, 100.0%] answer; 91.7% +/- 14.4% [55.8%, 100.0%] trace | 91.7% +/- 14.4% [55.8%, 100.0%] answer; 91.7% +/- 14.4% [55.8%, 100.0%] trace | 91.7% +/- 14.4% [55.8%, 100.0%] answer; 91.7% +/- 14.4% [55.8%, 100.0%] trace |
| quartic_factorization | 2 | 66.7% +/- 28.9% [0.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace | 66.7% +/- 28.9% [0.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace | 66.7% +/- 28.9% [0.0%, 100.0%] answer; 100.0% +/- 0.0% [100.0%, 100.0%] trace |
| rational_equation | 6 | 94.4% +/- 9.6% [70.5%, 100.0%] answer; 94.4% +/- 9.6% [70.5%, 100.0%] trace | 94.4% +/- 9.6% [70.5%, 100.0%] answer; 94.4% +/- 9.6% [70.5%, 100.0%] trace | 94.4% +/- 9.6% [70.5%, 100.0%] answer; 94.4% +/- 9.6% [70.5%, 100.0%] trace |
| repeated_quadratic_root | 4 | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 91.7% +/- 14.4% [55.8%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 91.7% +/- 14.4% [55.8%, 100.0%] trace | 100.0% +/- 0.0% [100.0%, 100.0%] answer; 91.7% +/- 14.4% [55.8%, 100.0%] trace |
| repeated_quartic_root | 1 | 66.7% +/- 57.7% [0.0%, 100.0%] answer; 66.7% +/- 57.7% [0.0%, 100.0%] trace | 66.7% +/- 57.7% [0.0%, 100.0%] answer; 66.7% +/- 57.7% [0.0%, 100.0%] trace | 66.7% +/- 57.7% [0.0%, 100.0%] answer; 66.7% +/- 57.7% [0.0%, 100.0%] trace |
| repeated_quintic_root | 1 | 66.7% +/- 57.7% [0.0%, 100.0%] answer; 66.7% +/- 57.7% [0.0%, 100.0%] trace | 66.7% +/- 57.7% [0.0%, 100.0%] answer; 66.7% +/- 57.7% [0.0%, 100.0%] trace | 66.7% +/- 57.7% [0.0%, 100.0%] answer; 66.7% +/- 57.7% [0.0%, 100.0%] trace |

Interpretation: values summarize seed variation; they are not problem-sampling confidence intervals.
