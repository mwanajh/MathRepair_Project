# Repeated-Seed MathRepair Evaluation

Trials: 5 | Base seeds: 500, 20500, 40500, 60500, 80500
Model: `qwen2-math:1.5b`
Temperature: `1.4` | Samples/problem: `3`
Problem set: `stress_model_problems.csv` (12 problems)

Values are mean +/- sample SD with a 95% Student-t interval.

| Strategy | Answer accuracy | Valid traces | Extra calls | Extra tokens |
|---|---:|---:|---:|---:|
| no_repair | 84.4% +/- 3.2% [80.5%, 88.4%] | 82.8% +/- 3.6% [78.3%, 87.3%] | 0.0 +/- 0.0 [0.0, 0.0] | 0.0 +/- 0.0 [0.0, 0.0] |
| verified_global_regeneration | 88.9% +/- 2.0% [86.5%, 91.3%] | 88.9% +/- 2.0% [86.5%, 91.3%] | 9.8 +/- 1.8 [7.6, 12.0] | 4949.2 +/- 899.1 [3833.0, 6065.4] |
| verified_local_repair | 97.8% +/- 3.0% [94.0%, 100.0%] | 97.2% +/- 2.8% [93.8%, 100.0%] | 7.6 +/- 2.3 [4.7, 10.5] | 5984.2 +/- 1650.2 [3935.6, 8032.8] |

## Paired Local Minus Global

| Metric | Mean +/- SD [95% CI] |
|---|---:|
| Answer accuracy difference | 8.9% +/- 4.6% [3.2%, 14.6%] |
| Trace-validity difference | 8.3% +/- 4.4% [2.9%, 13.8%] |

Answer advantage excludes zero at 95%: **True**
Trace advantage excludes zero at 95%: **True**

All matched-budget comparisons valid: **True**

## Caveats

- 5 trials provide only a preliminary variance estimate.
- Student-t intervals use 4 degrees of freedom.
- The evaluation set has 12 problems and is not a benchmark.
- Trials reuse the same problems, so intervals reflect seed variation rather than problem-sampling uncertainty.
- GPU sampling may vary even when base seeds are recorded.
- The problem-set hash is recorded to prevent cross-set aggregation.
