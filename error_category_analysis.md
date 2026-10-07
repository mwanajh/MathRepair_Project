# Error-Category Repair Analysis

Detected error runs: 7

| Error category | Cases | Global regeneration | Uniform local | Adaptive local | Best observed | Evidence |
|---|---:|---:|---:|---:|---|---|
| arithmetic_error | 1 | 0/1 (0.0%) | 0/1 (0.0%) | 0/1 (0.0%) | -- | sparse |
| algebraic_transformation_error | 5 | 2/5 (40.0%) | 1/5 (20.0%) | 1/5 (20.0%) | global_regeneration | counted |
| missing_assumption | 0 | 0/0 (--) | 0/0 (--) | 0/0 (--) | -- | unobserved |
| dependency_error | 0 | 0/0 (--) | 0/0 (--) | 0/0 (--) | -- | unobserved |
| incomplete_solution | 0 | 0/0 (--) | 0/0 (--) | 0/0 (--) | -- | unobserved |
| sign_error | 1 | 1/1 (100.0%) | 0/1 (0.0%) | 1/1 (100.0%) | -- | sparse |
| logical_inference_error | 0 | 0/0 (--) | 0/0 (--) | 0/0 (--) | -- | unobserved |
| semantic_interpretation_error | 0 | 0/0 (--) | 0/0 (--) | 0/0 (--) | -- | unobserved |

## Interpretation

algebraic_transformation_error has 5 runs; the higher repair rate in this pilot is global_regeneration. arithmetic_error, sign_error have fewer than 3 runs, so no strategy is selected. missing_assumption, dependency_error, incomplete_solution, logical_inference_error, semantic_interpretation_error were not observed. An empty cell is not a repair result.

## Limitations

- Only seven detected-error runs are available.
- Five of the seven runs are algebraic-transformation errors.
- Rates describe this matched-budget pilot, not general error-type behavior.
- A strategy is named only when a category has at least three detected-error runs.
- Unobserved categories are not evidence of zero repair success.
