# MathRepair repair-policy findings

## Current evidence

The original ablation run showed that the repair pipeline could modify a
baseline answer that was already correct. The full MathRepair arm attempted 20
repairs and produced 3 regressions.

The baseline-answer guard was added before verifier localization. In the
guarded rerun, the full arm had:

| Metric | Original | Guarded |
|---|---:|---:|
| Final-answer accuracy | 5.0% | 12.5% |
| Repair attempts | 20 | 17 |
| Repair successes | 1 | 1 |
| Regressions | 3 | 0 |

This supports the conclusion that false-positive repair was a real failure mode.

## Follow-up interventions

The following interventions were evaluated on the same 40-problem baseline:

- clean-trace hard negatives for the learned verifier;
- a trace-validity gate;
- a second local-repair attempt for invalid output;
- global regeneration after an unsuccessful local repair.

The retry increased valid repair generations from 10 to 17, but repair success
remained 1 and final accuracy remained 12.5%. The global fallback also kept
final accuracy at 12.5%. The trace gate increased token use without improving
accuracy.

## Architecture decision

The default policy is therefore conservative:

1. Preserve a baseline whose final answer is already correct.
2. Localize and repair only an incorrect baseline.
3. Preserve the original when repair cannot be verified.
4. Keep retry and global regeneration as experimental arms.

The next research bottleneck is repair quality on incorrect MATH traces. The
next dataset should label the correct repair target and include hard negative
valid traces, while evaluation should report repair success, regression rate,
correct-solution preservation, and token cost separately.

## Reproducibility artifacts

- `math500_system_ablation_report.json`: original run
- `math500_system_ablation_guarded_report.json`: baseline-answer guard
- `math500_system_ablation_retry_report.json`: guard plus retry
- `math500_system_ablation_fallback_report.json`: guard, retry, and fallback
- `learned_verifier_trace_gate_report.json`: trace-gate verifier pilot
