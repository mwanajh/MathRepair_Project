# Repeated-Seed MathRepair Evaluation

Trials: 3 | Base seeds: 160500, 180500, 200500
Model: `qwen2-math:1.5b`
Temperature: `1.4` | Samples/problem: `1`
Problem set: `expanded_heldout_model_problems.csv` (36 problems)

Values are mean +/- sample SD with a 95% Student-t interval.

| Strategy | Answer accuracy | Valid traces | Extra calls | Extra tokens |
|---|---:|---:|---:|---:|
| no_repair | 90.7% +/- 1.6% [86.8%, 94.7%] | 88.0% +/- 4.2% [77.4%, 98.5%] | 0.0 +/- 0.0 [0.0, 0.0] | 0.0 +/- 0.0 [0.0, 0.0] |
| verified_global_regeneration | 92.6% +/- 1.6% [88.6%, 96.6%] | 92.6% +/- 1.6% [88.6%, 96.6%] | 7.7 +/- 2.5 [1.4, 13.9] | 4236.0 +/- 1301.3 [1003.0, 7469.0] |
| verified_local_repair | 100.0% +/- 0.0% [100.0%, 100.0%] | 100.0% +/- 0.0% [100.0%, 100.0%] | 5.3 +/- 2.5 [-0.9, 11.6] | 4602.0 +/- 1538.6 [779.5, 8424.5] |

## Paired Local Minus Global

| Metric | Mean +/- SD [95% CI] |
|---|---:|
| Answer accuracy difference | 7.4% +/- 1.6% [3.4%, 11.4%] |
| Trace-validity difference | 7.4% +/- 1.6% [3.4%, 11.4%] |

Answer advantage excludes zero at 95%: **True**
Trace advantage excludes zero at 95%: **True**

All matched-budget comparisons valid: **True**

## Caveats

- 3 trials provide only a preliminary variance estimate.
- Student-t intervals use 2 degrees of freedom.
- The evaluation set has 36 problems and is not a benchmark.
- Trials reuse the same problems, so intervals reflect seed variation rather than problem-sampling uncertainty.
- GPU sampling may vary even when base seeds are recorded.
- The problem-set hash is recorded to prevent cross-set aggregation.
