# Parser-Normalized Sensitivity Analysis

Trials: `3` | Runs: `108`
Strict failures: `24` | Recovered outputs: `24` | Unrecovered: `0`
Recovered outputs with isolated answers: `22`

| Metric | Strict pipeline | Parser-normalized | Difference |
|---|---:|---:|---:|
| Answer accuracy | 47.2% | 59.3% | +12.0 pp |
| Valid traces | 44.4% | 56.5% | +12.0 pp |

Recovered correct answers: `13` | Recovered valid traces: `13`

Caveat: This offline sensitivity analysis changes parser handling only. It does not replace the primary end-to-end comparison.
