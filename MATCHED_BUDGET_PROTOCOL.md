# Matched-Budget Repair Protocol

## Research Question

Under the same additional prompt-plus-completion token ceiling, which strategy
produces the highest answer accuracy and valid-trace rate?

The comparison unit is one initially generated model trace. The primary
denominator includes every scheduled run, including failed generations. Repair
is eligible only when the shared verifier rejects a completed initial trace.

## Strategies

| ID | Strategy | Intervention |
| --- | --- | --- |
| A | Global regeneration | Regenerate a complete solution and accept it only if the shared verifier passes it. |
| B | Local repair, uniform | Give every detected-error run the same additional token ceiling and regenerate only its invalid suffix. |
| C | Local repair, adaptive | Divide the same total additional ceiling using a pre-registered risk score based on error type, error position, and affected suffix length; regenerate only the invalid suffix. |

`no_repair` is reported as context but is not one of the three repair
strategies.

## Budget Rule

Let `B` be the total prompt-plus-completion tokens consumed by the recorded local
repair attempts on the eligible runs.

- A receives per-run ceilings equal to the corresponding recorded local repair
  ceiling. Unused tokens are not transferred after an accepted regeneration.
- B receives `floor(B / error_run_count)` tokens per eligible run.
- C receives integer token ceilings summing exactly to `B`, allocated by the
  deterministic adaptive risk score.

Both allocated ceilings and actual tokens are reported. Accuracy is interpreted
under the ceiling, while actual token use is reported as compute utilization.
No strategy may accept a candidate that crosses its assigned ceiling.

## Metrics

| Metric | Definition |
| --- | --- |
| Answer accuracy | Runs whose final selected answer matches the reference divided by all scheduled runs. |
| Valid-trace rate | Runs whose final trace passes the shared symbolic verifier divided by all scheduled runs. |
| Repair success | Accepted verified repairs divided by detected-error runs. |
| Average calls | Initial generation plus repair calls divided by all scheduled runs. |
| Average tokens | Initial generation plus actual repair tokens divided by all scheduled runs. |
| Total compute cost | Total prompt-plus-completion token equivalents. Dollar cost is not reported for local Ollama inference. |

## Current Pilot Interpretation

The current checked-in report uses fresh model calls for all three strategies.
Replay mode remains available as a deterministic allocation audit, but it must
be labeled separately and must not replace the live comparison. A larger
confirmatory run should keep the same model snapshot, problems, verifier gate,
and pre-registered budget across repeated seeds.

The current adaptive heuristic is not assumed to be superior. If it performs
worse, that is a result about this allocation rule, not evidence against all
adaptive allocation methods.
