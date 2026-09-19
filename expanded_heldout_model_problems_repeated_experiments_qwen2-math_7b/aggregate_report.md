# Repeated-Seed MathRepair Evaluation

Trials: 3 | Base seeds: 160500, 180500, 200500
Model: `qwen2-math:7b`
Temperature: `1.4` | Samples/problem: `1`
Problem set: `expanded_heldout_model_problems.csv` (36 problems)

Values are mean +/- sample SD with a 95% Student-t interval.

| Strategy | Answer accuracy | Valid traces | Extra calls | Extra tokens |
|---|---:|---:|---:|---:|
| no_repair | 13.0% +/- 7.0% [0.0%, 30.3%] | 13.0% +/- 7.0% [0.0%, 30.3%] | 0.0 +/- 0.0 [0.0, 0.0] | 0.0 +/- 0.0 [0.0, 0.0] |
| verified_global_regeneration | 13.9% +/- 7.3% [0.0%, 32.1%] | 13.9% +/- 7.3% [0.0%, 32.1%] | 2.7 +/- 2.5 [-3.6, 8.9] | 565.3 +/- 550.6 [-802.6, 1933.3] |
| verified_local_repair | 13.0% +/- 7.0% [0.0%, 30.3%] | 13.0% +/- 7.0% [0.0%, 30.3%] | 2.0 +/- 2.0 [-3.0, 7.0] | 619.0 +/- 630.8 [-948.2, 2186.2] |

## Paired Local Minus Global

| Metric | Mean +/- SD [95% CI] |
|---|---:|
| Answer accuracy difference | -0.9% +/- 1.6% [-4.9%, 3.1%] |
| Trace-validity difference | -0.9% +/- 1.6% [-4.9%, 3.1%] |

Answer advantage excludes zero at 95%: **False**
Trace advantage excludes zero at 95%: **False**

All matched-budget comparisons valid: **True**

## Caveats

- 3 trials provide only a preliminary variance estimate.
- Student-t intervals use 2 degrees of freedom.
- The evaluation set has 36 problems and is not a benchmark.
- Trials reuse the same problems, so intervals reflect seed variation rather than problem-sampling uncertainty.
- GPU sampling may vary even when base seeds are recorded.
- The problem-set hash is recorded to prevent cross-set aggregation.
