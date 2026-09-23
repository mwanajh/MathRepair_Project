# MathRepair Ablation Table

Model: `qwen2-math:1.5b` | Runs: 36 | Detected errors: 7 | Matched additional-token ceiling: 5,800

| Variant | Graph | Typed error | Adaptive compute | Repair | Symbolic tool | Answer accuracy | Valid trace | Repair success | Avg calls | Avg tokens | Total cost | Status |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| Full MathRepair | on | rule_based_proxy | on | local | on | 86.1% | 86.1% | 28.6% | 1.17 | 721.5 | 25,975 tokens | proxy_result |
| No graph | off | rule_based_proxy | on | local | on | -- | -- | -- | -- | -- | -- | planned |
| No typed error | on | off_binary_only | on | local | on | -- | -- | -- | -- | -- | -- | planned |
| No adaptive compute | on | rule_based_proxy | off_uniform | local | on | 86.1% | 83.3% | 14.3% | 1.25 | 772.1 | 27,796 tokens | measured |
| Global regeneration instead of local repair | on | rule_based_proxy | off_global | global | on | 88.9% | 88.9% | 42.9% | 1.25 | 757.4 | 27,265 tokens | measured |
| No symbolic tool | on | learned_pending | on | local | off | -- | -- | -- | -- | -- | -- | blocked_by_learned_verifier |

## Interpretation

Only rows marked measured may support an ablation claim. The full row is a rule-based proxy until the learned verifier is trained.

The two measured ablations currently show:

- No adaptive compute: answer-accuracy delta versus the full proxy = +0.0 pp.
- Global regeneration instead of local repair: answer-accuracy delta versus the full proxy = +2.8 pp.

## Remaining Runs

- No graph: Flatten nodes into a sequence and disable dependency impact propagation.
- No typed error: Use only valid/invalid labels and one generic local-resample action.
- No symbolic tool: Requires the learned verifier before symbolic acceptance can be removed.
