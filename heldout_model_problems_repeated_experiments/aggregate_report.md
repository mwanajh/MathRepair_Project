# Repeated-Seed MathRepair Evaluation

Trials: 3 | Base seeds: 100500, 120500, 140500
Model: `qwen2-math:1.5b`
Prompt profile: `default`
Temperature: `1.4` | Samples/problem: `1`
Problem set: `heldout_model_problems.csv` (18 problems)

Values are mean +/- sample SD with a 95% Student-t interval.

| Strategy | Answer accuracy | Valid traces | Extra calls | Extra tokens |
|---|---:|---:|---:|---:|
| no_repair | 96.3% +/- 3.2% [88.3%, 100.0%] | 90.7% +/- 6.4% [74.8%, 100.0%] | 0.0 +/- 0.0 [0.0, 0.0] | 0.0 +/- 0.0 [0.0, 0.0] |
| verified_global_regeneration | 98.1% +/- 3.2% [90.2%, 100.0%] | 96.3% +/- 6.4% [80.4%, 100.0%] | 2.7 +/- 1.5 [-1.1, 6.5] | 1618.0 +/- 996.3 [-857.1, 4093.1] |
| verified_local_repair | 100.0% +/- 0.0% [100.0%, 100.0%] | 96.3% +/- 3.2% [88.3%, 100.0%] | 3.0 +/- 1.7 [-1.3, 7.3] | 2033.3 +/- 1104.8 [-711.3, 4778.0] |

## Paired Local Minus Global

| Metric | Mean +/- SD [95% CI] |
|---|---:|
| Answer accuracy difference | 1.9% +/- 3.2% [-6.1%, 9.8%] |
| Trace-validity difference | 0.0% +/- 5.6% [-13.8%, 13.8%] |

Answer advantage excludes zero at 95%: **False**
Trace advantage excludes zero at 95%: **False**

All matched-budget comparisons valid: **True**

## Caveats

- 3 trials provide only a preliminary variance estimate.
- Student-t intervals use 2 degrees of freedom.
- The evaluation set has 18 problems and is not a benchmark.
- Trials reuse the same problems, so intervals reflect seed variation rather than problem-sampling uncertainty.
- GPU sampling may vary even when base seeds are recorded.
- The problem-set hash is recorded to prevent cross-set aggregation.
