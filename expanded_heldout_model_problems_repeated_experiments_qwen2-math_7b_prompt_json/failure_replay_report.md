# Failure Replay By Category

Trials: `3` | Planned runs: `108`

Rates use planned runs in each category as the denominator.

| Category | Planned | Failures | Strict answer | Local answer | Normalized recovery | Normalized answer |
|---|---:|---:|---:|---:|---:|---:|
| cubic_factorization | 6 | 1 | 83.3% | 83.3% | 100.0% | 100.0% |
| cubic_transformation | 6 | 4 | 33.3% | 33.3% | 25.0% | 50.0% |
| large_coefficients | 12 | 0 | 91.7% | 100.0% | 0.0% | 91.7% |
| large_fractions | 18 | 2 | 38.9% | 77.8% | 100.0% | 50.0% |
| nested_distribution | 12 | 0 | 66.7% | 91.7% | 0.0% | 66.7% |
| nested_subtraction | 12 | 0 | 91.7% | 91.7% | 0.0% | 91.7% |
| quartic_factorization | 6 | 0 | 66.7% | 66.7% | 0.0% | 66.7% |
| rational_equation | 18 | 1 | 94.4% | 94.4% | 100.0% | 100.0% |
| repeated_quadratic_root | 12 | 0 | 100.0% | 100.0% | 0.0% | 100.0% |
| repeated_quartic_root | 3 | 1 | 66.7% | 66.7% | 0.0% | 66.7% |
| repeated_quintic_root | 3 | 1 | 66.7% | 66.7% | 0.0% | 66.7% |

Failure recovery types: `{'parser_failure': 5, 'recovered_valid_trace': 5}`

Caveat: Offline replay changes parser handling only for saved generation failures; it does not rerun model generation.
