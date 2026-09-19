# MathRepair Research Results Summary

The thesis-ready consolidated interpretation is in
[THESIS_RESULTS_CHAPTER.md](THESIS_RESULTS_CHAPTER.md).
The abstract and conclusion draft are in
[THESIS_ABSTRACT_AND_CONCLUSION.md](THESIS_ABSTRACT_AND_CONCLUSION.md).

## Current setup

- Model: `qwen2-math:1.5b`
- Backend: Ollama local API
- Task: one-variable symbolic algebra equations
- Repair comparison: no repair, verified global regeneration, verified local repair
- Verification: symbolic equation-chain verifier

## Stress evaluation

Five base seeds, 12 problems, 3 samples per problem, 36 runs per trial.

| Strategy | Mean answer accuracy | Mean valid traces |
|---|---:|---:|
| No repair | 84.4% | 82.8% |
| Global regeneration | 88.9% | 88.9% |
| Local repair | 97.8% | 97.2% |

Paired local-minus-global answer difference: `+8.9` percentage points, 95% CI
`[3.2, 14.6]`.

## Held-out evaluation

Three seeds, 18 problems, one sample per problem, 18 runs per trial.

| Strategy | Mean answer accuracy | Mean valid traces |
|---|---:|---:|
| No repair | 96.3% | 90.7% |
| Global regeneration | 98.1% | 96.3% |
| Local repair | 100.0% | 96.3% |

Paired local-minus-global answer difference: `+1.9` percentage points, 95% CI
`[-6.1, 9.8]`. This result is not statistically conclusive.

## Expanded evaluation

Three seeds, 36 problems, one sample per problem, 36 runs per trial. The set
contains the original 18 held-out problems plus 18 new problems.

| Strategy | Mean answer accuracy | Mean valid traces |
|---|---:|---:|
| No repair | 90.7% | 88.0% |
| Global regeneration | 92.6% | 92.6% |
| Local repair | 100.0% | 100.0% |

Paired local-minus-global answer difference: `+7.4` percentage points, 95% CI
`[3.4, 11.4]`.

Typed error analysis across the 3 expanded trials detected 13 invalid traces:
12 algebraic-transformation errors and 1 arithmetic error. Model repairs were
accepted in `13/13` detected cases, corrected 10 wrong answers, and produced no
answer regressions. These counts are aggregated run outcomes, not independent
problem samples.

## Interpretation

The current evidence supports the engineering hypothesis that verified local
repair can recover wrong or invalid reasoning under a matched per-error budget.
The expanded evaluation strengthens the result compared with the first held-out
set, but it is still not a formal benchmark: the problems are one-variable
algebra, the model is small, and the expanded set includes the original held-out
problems.

## 3B model comparison

`qwen2.5:3b` was evaluated on the same expanded set with seeds `160500`,
`180500`, and `200500`, temperature `1.4`, and one sample per problem.

| Strategy | 1.5B answer accuracy | 3B answer accuracy | 3B minus 1.5B |
|---|---:|---:|---:|
| No repair | 90.7% | 47.2% | -43.5 pp |
| Global regeneration | 92.6% | 56.5% | -36.1 pp |
| Local repair | 100.0% | 48.1% | -51.9 pp |

The candidate completed `84/108` parseable runs; the `24/108` generation
failures remained in the denominator as unsuccessful runs. Within this
candidate model, the local-minus-global answer difference was `-8.3` pp, with
a 95% CI of `[-15.2, -1.4]`. Therefore, this 3B candidate did not improve the
baseline, and verified global regeneration was better than local repair for
this model.

Many failures came from output formats the pipeline could not parse, especially
LaTeX and intermediate substitution variables. This is part of the observed
end-to-end robustness, but model capability and parser compatibility should be
separated in the next analysis.

The offline parser-normalized sensitivity analysis recovered all 24 raw
outputs. Of these, 13 had correct answers and valid traces; 11 remained
reasoning errors even after formatting was fixed. Candidate no-repair answer
accuracy rose from `47.2%` to `59.3%` (`+12.0` pp), and trace validity rose from
`44.4%` to `56.5%` (`+12.0` pp). Thus, parser compatibility explains part of
the gap, but the normalized candidate was still `31.5` pp below the baseline
in answer accuracy.

The sensitivity report is in
`expanded_heldout_model_problems_repeated_experiments_qwen2.5_3b/parser_sensitivity_report.md`.

## 7B math-model comparison

`qwen2-math:7b` was evaluated with the same expanded-set protocol. This model
has `7.6B` parameters, `Q4_0` quantization, and a local artifact of approximately
`4.43 GB`.

| Strategy | 1.5B answer accuracy | 7B answer accuracy | 7B minus 1.5B |
|---|---:|---:|---:|
| No repair | 90.7% | 13.0% | -77.8 pp |
| Global regeneration | 92.6% | 13.9% | -78.7 pp |
| Local repair | 100.0% | 13.0% | -87.0 pp |

The candidate completed `17/108` parseable runs; the `91/108` generation
failures remained in the denominator. Within the 7B candidate, the
local-minus-global answer difference was `-0.9` pp, with a 95% CI of
`[-4.9, 3.1]`, so these strategies did not show a statistically conclusive
difference in these trials.

The parser-normalized sensitivity analysis recovered `36/91` outputs: 31 had
correct answers and 29 had valid traces. No-repair answer accuracy rose from
`13.0%` to `41.7%` (`+28.7` pp), while trace validity rose from `13.0%` to
`39.8%` (`+26.9` pp). The remaining `55/91` outputs could not be recovered.
Therefore, output-format incompatibility explains a large part of the primary
result, but even the sensitivity result remained `49.1` pp below the baseline
answer accuracy.

The primary comparison is in
`expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b/model_comparison.md`;
sensitivity report is in the same directory.

## Next research step

Before testing another model, isolate the output-contract effect with a
model-specific prompt/parser experiment while leaving this primary protocol
frozen. Keep primary end-to-end and parser-normalized sensitivity results
separate so format compatibility is not confused with mathematical reasoning
quality.

The experiment harness provides an opt-in `qwen2_math_json` profile. It
requests Ollama JSON mode and plain-ASCII equation strings, and its parser
discards explanatory (non-equation) entries inside a Qwen `steps` array. The
default profile remains the primary protocol. Trial reports record
`prompt_profile`, and aggregation rejects mixed profiles.

## 7B model-specific prompt/parser experiment

The profile was run on the same expanded set with the same three seeds,
temperature, and sample count as the primary 7B comparison (108 planned
runs). Reports are in
`expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b_prompt_json/`.

| Strategy | Primary 7B | `qwen2_math_json` | Change |
|---|---:|---:|---:|
| No repair | 13.0% | 75.0% | +62.0 pp |
| Global regeneration | 13.9% | 75.9% | +62.0 pp |
| Local repair | 13.0% | 85.2% | +72.2 pp |

The profile reduced generation failures from `91/108` to `10/108`. Its
parser-normalized sensitivity result was `79.6%` answer accuracy and `80.6%`
valid traces, with `5/10` strict failures recovered offline. Compared with
the 1.5B baseline, the profile remained lower by `15.7` percentage points for
no repair, `16.7` for global regeneration, and `14.8` for local repair.
Therefore the original 7B result was dominated by output-contract
incompatibility, but the remaining normalized gap shows that prompt/parser
compatibility does not fully explain the model difference.

The profile's local-minus-global answer advantage was `+9.3` pp with a 95%
interval of `[+5.3, +13.2]`; this is evidence for local repair within the
profile, subject to the same three-trial and non-benchmark caveats.

Residual-failure analysis shows the profile is strongest on rational equations
(`94.4%` no-repair answer accuracy), nested subtraction (`91.7%`), and large
coefficients (`91.7%`). The main weak category is large fractions (`38.9%`
no-repair, `77.8%` after local repair), followed by cubic transformation
(`33.3%` no-repair). Across completed runs, the typed analyzer found `15`
algebraic-transformation errors and `1` arithmetic error; model repair
accepted `11/16` and corrected `11` wrong answers without regressions.
Category denominators now include generation failures so seed comparisons are
defined consistently. Details are in
`expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b_prompt_json/category_report.md`
and `error_report.md`.

The saved-failure replay makes the remaining format/reasoning split explicit:
`5/10` generation failures were recoverable as valid traces, while `5/10`
remained parser failures. Cubic transformation had `4/6` generation failures
and only `33.3%` strict answer accuracy; large fractions had `2/18`
generation failures, but its low strict accuracy was mainly completed
reasoning errors that local repair improved. The replay table is in
`expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b_prompt_json/failure_replay_report.md`.
