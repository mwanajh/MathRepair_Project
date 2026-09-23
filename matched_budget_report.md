# Matched-Budget Repair Comparison

Model: `qwen2-math:1.5b` | Runs: 36 | Detected errors: 7

Budget rule: Each repair strategy receives approximately the same total additional prompt-plus-completion token ceiling across detected error runs. Global retains recorded per-run ceilings; uniform and adaptive local repair redistribute the shared total.

| Strategy | Answer accuracy | Valid traces | Repair success | Avg calls | Avg tokens | Total compute cost |
|---|---:|---:|---:|---:|---:|---:|
| no_repair | 86.1% (31/36) | 80.6% (29/36) | 0.0% (0/7) | 1.00 | 624.1 | 22,469 tokens |
| verified_global_regeneration | 88.9% (32/36) | 88.9% (32/36) | 42.9% (3/7) | 1.25 | 757.4 | 27,265 tokens |
| verified_local_repair_uniform | 86.1% (31/36) | 83.3% (30/36) | 14.3% (1/7) | 1.25 | 772.1 | 27,796 tokens |
| verified_local_repair_adaptive | 86.1% (31/36) | 86.1% (31/36) | 28.6% (2/7) | 1.17 | 721.5 | 25,975 tokens |

Global budget utilization: 82.7%
Matched additional-token ceiling: 5,800
Matched-budget comparison valid: **True**
Uniform local minus global answer accuracy: -2.8 pp
Adaptive local minus global answer accuracy: -2.8 pp

## Caveats

- This is a small stress set and not a benchmark result.
- Both repair strategies use the same symbolic verifier gate.
- Global regeneration retries only while its per-error budget remains.
- Uniform and adaptive local strategies use fresh model calls.
- Adaptive local caps use trace depth and typed-error risk as a pre-registered heuristic.
- GPU sampling may vary slightly even with recorded seeds.
