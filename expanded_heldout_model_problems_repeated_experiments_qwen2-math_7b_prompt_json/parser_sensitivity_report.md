# Parser-Normalized Sensitivity Analysis

Trials: `3` | Runs: `108`
Strict failures: `10` | Recovered outputs: `5` | Unrecovered: `5`
Recovered outputs with isolated answers: `4`

| Metric | Strict pipeline | Parser-normalized | Difference |
|---|---:|---:|---:|
| Answer accuracy | 75.0% | 79.6% | +4.6 pp |
| Valid traces | 75.9% | 80.6% | +4.6 pp |

Recovered correct answers: `5` | Recovered valid traces: `5`

Caveat: This offline sensitivity analysis changes parser handling only. It does not replace the primary end-to-end comparison.
