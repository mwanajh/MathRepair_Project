# MathRepair: supervisor feedback brief

## Decision needed

Should the primary MathRepair system prioritize conservative preservation of
verified answers, or should the next phase prioritize improving repair quality
even when this temporarily increases regression risk?

## What was changed

The ablation pipeline was corrected so the primary evaluation does not use the
reference answer to decide whether to repair. The reference answer is used only
for post-hoc scoring. A guarded version is retained as a comparison condition.

## Main results on the same 40-problem baseline

| Configuration | Final accuracy | Repair successes | Regressions |
|---|---:|---:|---:|
| Original guarded run | 12.5% | 1 | 0 |
| Primary unguarded run | 2.5% | 1 | 4 |

The unguarded result is the realistic system result because it does not access
the reference answer before repair. The guarded result is reported only as an
ablation showing the effect of preserving answers known to be correct.

## Additional interventions

- A second local-generation attempt increased valid output generation but did
  not increase repair success.
- Global regeneration after failed local repair did not increase final accuracy.
- A trace-validity classifier achieved only 66.67% pair accuracy in the pilot;
  it is not yet safe to add to the primary pipeline.

## Current interpretation

The largest observed failure mode is verifier over-triggering: it localizes an
error in traces that may already be correct, then the repair step damages them.
The second bottleneck is repair quality on genuinely incorrect traces. Output
format retries improve JSON validity but not mathematical correctness.

## Questions for supervisor

1. Should the unguarded 2.5% result be the main reported system result, with
   the 12.5% guarded run presented as an ablation?
2. Should MathRepair include an abstention policy that preserves uncertain
   traces, even if this lowers the number of repair attempts?
3. Should the next experiment focus on a better verifier dataset, or on a
   stronger repair model for the already-localized error cases?
4. Is the current 40-problem pilot sufficient for the next iteration, or should
   we first expand the evaluation set?

## Reproducibility artifacts

- `math500_system_ablation_ungarded_report.json`
- `math500_system_ablation_clean_report.json`
- `math500_system_ablation_guarded_report.json`
- `math500_system_ablation_retry_report.json`
- `math500_system_ablation_fallback_report.json`
- `trace_validity_experiment.py`
