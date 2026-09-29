# Error-Category Repair Analysis

Detected error runs: 7

| Error category | Cases | Global regeneration | Uniform local | Adaptive local | Best observed | Evidence |
|---|---:|---:|---:|---:|---|---|
| arithmetic_error | 1 | 0/1 (0.0%) | 0/1 (0.0%) | 0/1 (0.0%) | tie | observed |
| algebraic_transformation_error | 5 | 2/5 (40.0%) | 1/5 (20.0%) | 1/5 (20.0%) | global_regeneration | observed |
| missing_assumption | 0 | 0/0 (--) | 0/0 (--) | 0/0 (--) | -- | no_observed_cases |
| dependency_error | 0 | 0/0 (--) | 0/0 (--) | 0/0 (--) | -- | no_observed_cases |
| incomplete_solution | 0 | 0/0 (--) | 0/0 (--) | 0/0 (--) | -- | no_observed_cases |
| sign_error | 1 | 1/1 (100.0%) | 0/1 (0.0%) | 1/1 (100.0%) | tie | observed |
| logical_inference_error | 0 | 0/0 (--) | 0/0 (--) | 0/0 (--) | -- | no_observed_cases |
| semantic_interpretation_error | 0 | 0/0 (--) | 0/0 (--) | 0/0 (--) | -- | no_observed_cases |

## Interpretation

Global regeneration was stronger on the observed algebraic-transformation cases, while adaptive local repair matched global regeneration on the one observed sign-error case. The arithmetic case produced no accepted repair for either strategy. Missing-assumption, dependency, incomplete-solution, logical-inference, and semantic-interpretation categories were not observed in this seven-error pilot and require targeted data before comparison.

## Limitations

- Only seven detected-error runs are available.
- Five of the seven runs are algebraic-transformation errors.
- Rates describe this matched-budget pilot, not general error-type behavior.
- Unobserved categories are not evidence of zero repair success.
