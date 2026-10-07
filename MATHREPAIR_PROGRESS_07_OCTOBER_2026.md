# MathRepair progress, 7 October 2026

## Question

Can the system tell a real model trace that should be left alone from one that needs a particular recovery action, and can it refuse a repair that is not more reliable than the original?

The measured MATH-500 system result is still the unguarded run of 6 October 2026. It is not replaced by any number below.

## Evidence that stays in force

On 40 level-4/5 MATH-500 problems, `qwen2.5:3b`, seed 42, temperature 0:

| Record | Final accuracy | Repair successes | Regressions | How the reference answer was used |
|---|---:|---:|---:|---|
| Report read earlier | 10% to 5% | 1 | 3 | The later code no longer matches that run |
| Unguarded run, 6 October 2026, 13:32 UTC | 10% to 2.5% | 1 of 29 attempts | 4 | Scoring only, after the repair decision |

The unguarded full arm detected an error on 29 of 30 completed traces and attempted 29 repairs. One repair corrected a wrong answer. Four repairs replaced a correct answer. The 12.5% runs are not the system result: those runs could see the reference answer before deciding whether to repair.

The earlier perfect verifier score was 8 synthetic test traces, one per error type. It is a pipeline check.

The algebra comparison remains a separate protocol: 36 problems, `qwen2-math:1.5b`, no repair 90.7%, global regeneration 92.6%, local repair 100%. It is not a MATH-500 result.

## 1. Natural-error dataset

Thirty-nine model traces are reviewed. One trace, `test/number_theory/1065.json`, is still unreviewed because the modulo sign in the step text is not readable. No label was invented for it.

| Item | Count |
|---|---:|
| Saved generations | 50 |
| Completed traces | 40 |
| Output failures | 10 |
| Reviewed | 39 |
| Valid, `VALID_NO_REPAIR`, action `CONTINUE` | 4 |
| Invalid | 35 |

Every required error type has at least 3 reviewed examples: arithmetic 7, algebraic transformation 4, sign 3, missing assumption 3, logical inference 5, semantic interpretation 5, dependency 3, incomplete solution 5. A correct sampled answer was not used as `VALID_NO_REPAIR`. Six traces have a correct sampled answer, and 34 do not. Those flags are sampling records, not trace-validity labels.

`GLOBAL_REGENERATE` was not assigned. That empty action is not evidence that global regeneration fails.

Source: `natural_error_dataset_statistics.json`.

## 2. Verifier retrained on the reviewed traces

The same five stratified splits were used for three systems. Each test split has one trace of each class, including one valid trace. The numbers are means across those five splits.

| Metric | TF-IDF retrained on natural traces | Same TF-IDF features with SVD | Synthetic TF-IDF, not retrained |
|---|---:|---:|---:|
| Repair-trigger precision | 0.95 | 0.87 | 0.87 |
| Repair-trigger recall | 0.53 | 0.70 | 0.85 |
| False-positive repair rate | 0.20 | 0.80 | 1.00 |
| First-error location accuracy | 0.23 | 0.03 | 0.05 |
| First-error location F1 | 0.29 | 0.02 | 0.05 |
| Error-type macro-F1 | 0.08 | 0.02 | 0.14 |

`VALID_NO_REPAIR` is the abstention. The retrained TF-IDF model started a repair on the held-out valid trace in 1 of 5 splits. The synthetic model started a repair on that trace in every split. That is the same over-triggering that damaged correct MATH-500 answers.

The SVD projection was the stronger representation that was available without a new pretrained encoder. On this set it was weaker. Location accuracy for the retrained TF-IDF model ranged from 0 to 0.38 depending on the split. Type classification remains near the floor of a nine-class problem with one test example per class.

The reference answer, the annotation note, and the sampling flag were not features.

Source: `natural_verifier_report.json`.

## 3. Repair-acceptance gate

A generated repair no longer replaces the original trace on its own. The gate compares the two traces with the symbolic checker and never receives the reference answer. It accepts the replacement only when the repaired trace is symbolically verified and the original trace is not.

Checked behavior:

- A broken equation chain for `2(x + 3) = 14` is replaced by a symbolically verified chain ending at `x = 4`, even when the stored reference answer is a different string.
- A repaired equation that still has a symbolic error is rejected.
- A trace that is already symbolically verified is kept.
- An open-ended text repair is rejected even when the new text states the known answer. The original answer stays.

The 40-problem system was not run again after this gate. The 2.5% result therefore remains the measured system accuracy. The gate says what would be refused; it does not yet say what the 40-problem accuracy would become.

Source: `repair_acceptance.py`.

## 4. Frozen generation protocol

Five 10-problem pilots were compared. The frozen protocol is the one whose readable traces all met the strict JSON contract: `qwen2.5:3b`, text problems, prompt `stable_text_json`, temperature 0, base seed 42, 512 output tokens, and no repair during the baseline generation.

On that pilot, 5 of 10 traces were readable and all 5 were strict. None needed the recovery parser. Answer accuracy was 1/10. The other four pilots were less strict: `qwen2-math:1.5b` produced no readable trace, `qwen2-math:7b` produced 4 readable traces and 0 strict traces, and the other `qwen2.5:3b` prompts mixed strict traces with parser recovery.

Five unreadable traces out of ten are why a larger benchmark stays blocked. The earlier 40-problem baseline is a different contract: 1 strict trace and 29 parser recoveries. Its 10% accuracy is not a result of the frozen protocol.

## 5. Routing comparison

Three policies were scored on the 39 reviewed recovery labels. The score is agreement with the label. No repair was generated, and the final answer was not rescored.

Each test split has one trace for each observed action. Means over five splits:

| Policy | Agreement with the reviewed action | Macro-F1 |
|---|---:|---:|
| A. Always `GLOBAL_REGENERATE` | 0.00 | 0.00 |
| B. Always `LOCAL_REPAIR` | 0.20 | 0.07 |
| C. TF-IDF router | 0.32 | 0.18 |

The learned router ranged from 0.20 to 0.40, which is one or two of the five held-out traces. Policy A agrees with nothing because `GLOBAL_REGENERATE` has no reviewed example. That is an empty category, not a repair-quality result.

Reviewed action counts: `BACKTRACK` 14, `REPLAN` 10, `TOOL_EXECUTE` 7, `CONTINUE` 4, `LOCAL_REPAIR` 4, `GLOBAL_REGENERATE` 0.

Source: `recovery_routing_report.json`.

## 6. Error category and recovery label

Repair outcomes and review labels are separate tables.

The only repair-outcome cell with at least three runs is the older matched-budget pilot: `algebraic_transformation_error`, 5 runs, global regeneration 2/5, adaptive local repair 1/5. `arithmetic_error` and `sign_error` have one run each, so no strategy is selected. Five error types were not in that pilot. An empty cell is not a repair result.

The 39 reviews name a recovery label only where every example of a type carries the same label and the type has at least three reviews:

| Error type | Reviews | Unanimous reviewed label |
|---|---:|---|
| `VALID_NO_REPAIR` | 4 | `CONTINUE` |
| `arithmetic_error` | 7 | `TOOL_EXECUTE` |
| `algebraic_transformation_error` | 4 | `LOCAL_REPAIR` |
| `sign_error` | 3 | `BACKTRACK` |
| `missing_assumption` | 3 | `BACKTRACK` |
| `logical_inference_error` | 5 | `BACKTRACK` |
| `semantic_interpretation_error` | 5 | `REPLAN` |
| `dependency_error` | 3 | `BACKTRACK` |
| `incomplete_solution` | 5 | `REPLAN` |

These are the labels written at review. They do not measure whether that action changes the final answer. `GLOBAL_REGENERATE` is 0 in every row.

Sources: `error_category_analysis.json`, `reviewed_error_category_analysis.json`.

## Failure analysis

1. The synthetic verifier still starts a repair on every held-out valid natural trace.
2. Retraining lowers that false-positive rate to one split in five, and the first-error location is still wrong on most invalid traces.
3. The acceptance gate can certify an equation repair. It cannot yet show that an open-ended MATH repair is more reliable, so it keeps the original text.
4. The frozen output protocol still leaves half of the 10-problem pilot unreadable.
5. Learned routing agrees with the reviewed action only slightly more often than always choosing local repair, on five-trace tests.
6. No reviewed trace was labeled `GLOBAL_REGENERATE`, so a comparison of repair quality by that action is not available.
7. `test/number_theory/1065.json` remains unlabeled.

## What this week does not show

It does not show that MathRepair improves the 40-problem MATH-500 result. It does not show that the natural verifier locates or types real errors well enough to drive repair. It does not show that the acceptance gate raises accuracy. It does not show which recovery action repairs which error type.

## Questions

1. Should the unguarded 10% to 2.5% result remain the system number until a new run uses both the frozen protocol and the acceptance gate?
2. The natural verifier reduces false repairs and still misses the first error. Is the useful next step more reviewed traces, or a representation other than TF-IDF and SVD?
3. `GLOBAL_REGENERATE` has no reviewed examples. Should the next sample target traces that are wrong from the first step, before any outcome comparison of global and local repair?
4. On open-ended text, the gate keeps the original answer whenever the symbolic checker cannot compare the two states. Is that the abstention you want, or should a second non-gold signal be defined before another MATH-500 run?

## Repository

The sections above record the state before the closed JSON protocol was frozen. The measurement below is the later 40-problem run.

## Frozen 40-problem outcome comparison

The generation protocol is now frozen as `qwen2.5:3b`, `closed_text_json`, temperature 0, base seed 42, and 1024 output tokens. On the same 10-problem check, 10 of 10 traces were strict JSON and none was cut by the token limit. The earlier `stable_text_json` pilot, with 5 of 10 traces unreadable, is retained as evidence and is not this protocol.

The 40-problem subset was then generated once under the frozen protocol, with no repair. All 40 traces were strict JSON. One answer was correct, so the baseline accuracy is 1/40 (2.5%). This is not the earlier unguarded system result. That result remains 10% to 2.5% on the previous output contract: 1 of 29 repairs succeeded and 4 regressions occurred.

The natural TF-IDF verifier flagged 30 of the 40 traces. Three policies then ran, and the acceptance gate decided whether a candidate could replace the original. The gate did not see the reference answer.

| Policy | Repairs attempted | Candidates generated | Accepted | Final accuracy | False-positive replacements |
|---|---:|---:|---:|---:|---:|
| A. Always global regeneration | 30 | 30 | 0 | 1/40 (2.5%) | 0 |
| B. Always local repair | 30 | 27 | 0 | 1/40 (2.5%) | 0 |
| C. Learned router | 30 | 24 | 0 | 1/40 (2.5%) | 0 |

Every generated text candidate was rejected because the two traces were not symbolically comparable. The router also chose `TOOL_EXECUTE` on 5 flagged traces; the symbolic tool abstained. Three local repairs and one routed repair did not return valid JSON. No accepted repair changed a correct answer, so the false-positive replacement rate on the one initially correct answer is 0.

The candidate text was scored only after the gate. If those rejected candidates had replaced the original, global regeneration would have matched 2 reference answers, local repair 1, and the router 3. Those counts are not the system result.

On the 30 flagged traces the router chose `BACKTRACK` 16 times, `REPLAN` 7, `TOOL_EXECUTE` 5, and `LOCAL_REPAIR` 2. It did not choose `GLOBAL_REGENERATE`. The other 10 traces were left unchanged because the verifier did not locate an error.

The predicted-type table uses the natural verifier, not reviewed labels. A strategy is named only when one policy corrects more answers on at least three traces. Four predicted types reached that count, and none produced an accepted correction:

| Predicted type | Traces | Evidence | Best strategy |
|---|---:|---|---|
| `arithmetic_error` | 18 | counted | none |
| `logical_inference_error` | 4 | counted | none |
| `incomplete_solution` | 3 | counted | none |
| `semantic_interpretation_error` | 3 | counted | none |
| `algebraic_transformation_error` | 2 | sparse | none |
| `missing_assumption` | 0 | unobserved | none |
| `dependency_error` | 0 | unobserved | none |
| `sign_error` | 0 | unobserved | none |

An empty or sparse cell is not a failed strategy. The older algebraic outcome, global 2/5 against adaptive local 1/5, remains a separate five-run cell from the earlier protocol.

Sources: `frozen40_closed_baseline_report.json`, `frozen_outcome_comparison_report.json`.
