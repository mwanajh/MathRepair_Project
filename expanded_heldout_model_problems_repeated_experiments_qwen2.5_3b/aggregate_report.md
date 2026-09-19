# Repeated-Seed MathRepair Evaluation

Trials: 3 | Base seeds: 160500, 180500, 200500
Model: `qwen2.5:3b`
Temperature: `1.4` | Samples/problem: `1`
Problem set: `expanded_heldout_model_problems.csv` (36 problems)

Values are mean +/- sample SD with a 95% Student-t interval.

| Strategy | Answer accuracy | Valid traces | Extra calls | Extra tokens |
|---|---:|---:|---:|---:|
| no_repair | 47.2% +/- 2.8% [40.3%, 54.1%] | 44.4% +/- 2.8% [37.5%, 51.3%] | 0.0 +/- 0.0 [0.0, 0.0] | 0.0 +/- 0.0 [0.0, 0.0] |
| verified_global_regeneration | 56.5% +/- 4.2% [45.9%, 67.0%] | 54.6% +/- 5.8% [40.3%, 69.0%] | 27.7 +/- 2.5 [21.4, 33.9] | 6593.3 +/- 749.1 [4732.2, 8454.5] |
| verified_local_repair | 48.1% +/- 4.2% [37.6%, 58.7%] | 47.2% +/- 4.8% [35.3%, 59.2%] | 23.7 +/- 3.8 [14.3, 33.1] | 7961.3 +/- 874.7 [5788.2, 10134.5] |

## Paired Local Minus Global

| Metric | Mean +/- SD [95% CI] |
|---|---:|
| Answer accuracy difference | -8.3% +/- 2.8% [-15.2%, -1.4%] |
| Trace-validity difference | -7.4% +/- 1.6% [-11.4%, -3.4%] |

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
