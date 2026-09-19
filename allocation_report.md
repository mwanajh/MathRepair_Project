# Adaptive Compute Allocation Report

Problem: `2(x + 3) = 14`
Budget: `10` extra calls
Error node: `n1` (algebraic_transformation_error)
Affected nodes: `n2, n3`

| Node | Uncertainty | Importance | Propagation risk | Priority | Allocated calls |
|---|---:|---:|---:|---:|---:|
| n1 | 0.950 | 1.000 | 1.000 | 0.950 | 7 |
| n4 | 0.100 | 0.667 | 0.000 | 0.000 | 0 |
| n2 | 0.700 | 0.667 | 0.750 | 0.350 | 2 |
| n5 | 0.100 | 0.333 | 0.000 | 0.000 | 0 |
| n3 | 0.700 | 0.333 | 0.750 | 0.175 | 1 |

Interpretation: extra calls concentrate on the error node and its affected descendants; unaffected branches receive zero calls.
