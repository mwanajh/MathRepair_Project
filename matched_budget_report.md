# Matched-Budget Repair Comparison

Model: `qwen2-math:1.5b` | Runs: 36 | Detected errors: 7

Budget rule: Per error run, global prompt plus completion tokens may not exceed the prompt plus completion tokens used by local model repair.

| Strategy | Answer accuracy | Valid traces | Extra calls | Extra tokens |
|---|---:|---:|---:|---:|
| no_repair | 86.1% (31/36) | 80.6% (29/36) | 0 | 0 |
| verified_global_regeneration | 88.9% (32/36) | 88.9% (32/36) | 9 | 4,841 |
| verified_local_repair | 100.0% (36/36) | 97.2% (35/36) | 8 | 5,800 |

Global budget utilization: 83.5%
Matched-budget comparison valid: **True**

## Caveats

- This is a small stress set and not a benchmark result.
- Both repair strategies use the same symbolic verifier gate.
- Global regeneration retries only while its per-error budget remains.
- GPU sampling may vary slightly even with recorded seeds.
