# Repeated-Seed MathRepair Evaluation

Trials: 3 | Base seeds: 160500, 180500, 200500
Model: `qwen2-math:7b`
Prompt profile: `qwen2_math_json`
Temperature: `1.4` | Samples/problem: `1`
Problem set: `expanded_heldout_model_problems.csv` (36 problems)

Values are mean +/- sample SD with a 95% Student-t interval.

| Strategy | Answer accuracy | Valid traces | Extra calls | Extra tokens |
|---|---:|---:|---:|---:|
| no_repair | 75.0% +/- 5.6% [61.2%, 88.8%] | 75.9% +/- 5.8% [61.6%, 90.3%] | 0.0 +/- 0.0 [0.0, 0.0] | 0.0 +/- 0.0 [0.0, 0.0] |
| verified_global_regeneration | 75.9% +/- 4.2% [65.4%, 86.5%] | 76.9% +/- 4.2% [66.3%, 87.4%] | 12.3 +/- 5.1 [-0.4, 25.1] | 2430.7 +/- 1018.5 [-99.6, 4961.0] |
| verified_local_repair | 85.2% +/- 4.2% [74.6%, 95.7%] | 86.1% +/- 4.8% [74.2%, 98.1%] | 8.3 +/- 5.1 [-4.4, 21.1] | 2810.3 +/- 1335.5 [-507.5, 6128.1] |

## Paired Local Minus Global

| Metric | Mean +/- SD [95% CI] |
|---|---:|
| Answer accuracy difference | 9.3% +/- 1.6% [5.3%, 13.2%] |
| Trace-validity difference | 9.3% +/- 1.6% [5.3%, 13.2%] |

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
