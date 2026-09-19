# Parser-Normalized Sensitivity Analysis

Trials: `3` | Runs: `108`
Strict failures: `91` | Recovered outputs: `36` | Unrecovered: `55`
Recovered outputs with isolated answers: `33`

| Metric | Strict pipeline | Parser-normalized | Difference |
|---|---:|---:|---:|
| Answer accuracy | 13.0% | 41.7% | +28.7 pp |
| Valid traces | 13.0% | 39.8% | +26.9 pp |

Recovered correct answers: `31` | Recovered valid traces: `29`

Caveat: This offline sensitivity analysis changes parser handling only. It does not replace the primary end-to-end comparison.
