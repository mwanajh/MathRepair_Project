# MathRepair Ablation Protocol

## Purpose

This protocol freezes the ablation structure before all experiments are run.
It separates measured values from planned cells and prevents incomplete results
from being presented as evidence.

The primary question for each ablation is: how much does removing one MathRepair
component change answer accuracy under approximately matched compute?

## Frozen variants

| Variant | Single intended change | Current evidence |
|---|---|---|
| Full MathRepair | Reference configuration | Rule-based proxy only |
| No graph | Flatten the trace and disable dependency impact propagation | Planned |
| No typed error | Replace typed labels and actions with binary valid/invalid plus generic local resampling | Planned |
| No adaptive compute | Allocate a uniform local-repair budget | Measured in Task 5 |
| Global regeneration instead of local repair | Regenerate the whole trace within the matched ceiling | Measured in Task 5 |
| No symbolic tool | Remove symbolic verification and tool execution | Planned after the learned verifier exists |

The current reference row is not the final learned-verifier system. It is
explicitly labeled `proxy_result` because typed errors are still produced by
rules. It must not be described as a completed Full MathRepair result.

## Controlled variables

Within a completed ablation run, hold constant:

- problem IDs and ordering;
- base model and model checkpoint;
- prompts except for the component being removed;
- decoding temperature and seed schedule;
- initial traces;
- maximum prompt-plus-completion token budget;
- answer parser, correctness criterion, and reporting denominator.

Use paired runs when possible: each variant receives the same problem and base
trace. Record failures and exhausted budgets in the denominator.

## Metrics

The primary metric is answer accuracy. Secondary metrics are valid-trace rate,
repair success rate, average model calls, average tokens, and total compute cost
in prompt-plus-completion token equivalents. Provider-specific monetary cost may
be added only when a fixed price card is recorded.

The reported delta is `variant answer accuracy - reference answer accuracy` in
percentage points. The reference and variant must come from the same controlled
run before the delta can support a component-level claim.

## Evidence states

- `measured`: fresh model calls under a valid matched-budget comparison.
- `proxy_result`: measured pipeline result that does not yet instantiate the
  final learned-verifier design.
- `planned`: experiment defined but not run; every metric remains `null`.
- `blocked_by_learned_verifier`: cannot isolate the intended component until
  the learned verifier is available; every metric remains `null`.

Only `measured` rows may support ablation claims. A proxy may guide engineering
but is not final thesis evidence.

## Execution order

1. Train or select the typed learned verifier and rerun the reference system.
2. Run no typed error and no symbolic tool against that same reference.
3. Implement graph flattening and run no graph without changing other inputs.
4. Rerun no adaptive compute and global regeneration on the same benchmark,
   model, seeds, and budget used by the final reference.
5. Report paired differences and uncertainty intervals; do not infer superiority
   from the current 36-run stress pilot alone.

## Reproduction

Build the current partial table from the fresh Task 5 artifact:

```powershell
python ablation_table.py
```

This writes `ablation_table.json` for machine-readable results and
`ablation_table.md` for the paper-facing table. The builder rejects invalid or
replay-only matched-budget reports.
