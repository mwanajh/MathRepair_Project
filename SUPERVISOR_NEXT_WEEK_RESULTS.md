# MathRepair Next-Week Results

Updated: 29 September 2026

## Supervisor Deliverable Checklist

This report contains all five requested deliverables: learned-verifier results,
real 40-problem MATH-500 accuracy, the three key system ablations, error-type-wise
local-versus-global comparison, and a short current conclusion. Web-interface
work was not prioritized in this cycle.

## 1. Learned Typed Verifier

The first learned verifier uses TF-IDF features with logistic-regression heads
for first-error location and the frozen eight-class error taxonomy. The 48
controlled examples were split by whole trace into 32 train, 8 development, and
8 test examples, preserving every class in every partition.

| Method | Location accuracy | Type accuracy | End-to-end |
|---|---:|---:|---:|
| Learned typed verifier | 100.0% | 100.0% | 100.0% |
| Current structural/symbolic baseline | 50.0% | 50.0% | -- |

The baseline figures count abstentions as incorrect. Because the test has one
synthetic example per class and shares template structure with training, this is
a pipeline result rather than evidence of natural-trace generalization.

## 2. Full MATH-500 Hard-Subset Baseline

The frozen 40-problem subset was evaluated with `qwen2.5:3b`, seed 42,
temperature 0, a 1,024-token output cap, and no repair. Reference answers were
used only after generation for scoring.

| Metric | Result |
|---|---:|
| Problems | 40 |
| Completed generations | 30 |
| Output failures | 10 |
| Strict-contract outputs | 1 |
| Normalized recoveries | 29 |
| Correct final answers | 4 |
| Answer accuracy, failures included | 10.0% |
| Model calls | 40 |
| Prompt + completion tokens | 28,791 |

This result exposes both model-quality and output-contract limitations. The ten
failures remain in the denominator; normalized outputs are reported separately
from strict compliance.

## 3. Matched-Budget System Ablations

These ablations are important because they identify which part of MathRepair is
actually useful. The runs therefore keep the baseline generations, seeds, model,
answer scorer, problem order, and additional-token ceiling fixed across variants.
Null results and repair regressions are retained rather than omitted.

All variants reused the same baseline generations. The full arm established a
shared ceiling of 8,487 additional prompt-plus-completion tokens. Each detected
case received at most one repair call, with the same model, seeds, temperature,
problem order, and answer scorer.

| Variant | Initial | Final | Detections | Repair success | Regressions | Calls | Tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full MathRepair | 10.0% | 5.0% | 20 | 1/20 | 3 | 20 | 8,487 |
| No graph | 10.0% | 5.0% | 30 | 0/19 | 2 | 19 | 8,218 |
| No typed error | 10.0% | 5.0% | 20 | 1/20 | 3 | 20 | 8,107 |
| No symbolic/tool support | 10.0% | 5.0% | 20 | 1/20 | 3 | 20 | 8,487 |

The no-graph verifier detected errors in all 30 completed traces. Eleven repair
calls were skipped because the corresponding full-arm per-problem allocation
was zero, preserving the matched budget. Every arm respected the shared ceiling.

## Interpretation

The current learned verifier does not generalize safely from the controlled
training templates to hard open-ended MATH traces. Local repair corrected one
wrong answer in the full arm but also damaged three initially correct answers,
reducing final accuracy from 10.0% to 5.0%.

Removing graph features changed detection behavior but did not change final
accuracy. Removing typed-error information also did not change accuracy under
this small, low-performing setting. These are null pilot results, not proof that
the components are unnecessary.

The structural/symbolic heuristic abstained on every completed open-ended trace.
Therefore, the identical full and no-symbolic results show zero tool coverage in
this benchmark path; they do not show that symbolic support has no value.

## 4. Error-Category Analysis

The category question is: when does local repair help, and when does global
regeneration work better? The comparison unit is an accepted, answer-correct
repair among detected-error runs in the matched-budget algebra pilot.

| Error category | Cases | Global | Uniform local | Adaptive local | Best observed |
|---|---:|---:|---:|---:|---|
| Arithmetic error | 1 | 0/1 (0.0%) | 0/1 (0.0%) | 0/1 (0.0%) | Tie: neither succeeded |
| Algebraic transformation error | 5 | 2/5 (40.0%) | 1/5 (20.0%) | 1/5 (20.0%) | Global regeneration |
| Sign error | 1 | 1/1 (100.0%) | 0/1 (0.0%) | 1/1 (100.0%) | Tie: global/adaptive |
| Missing assumption | 0 | -- | -- | -- | No observed cases |
| Dependency error | 0 | -- | -- | -- | No observed cases |
| Incomplete reasoning | 0 | -- | -- | -- | No observed cases |

The observed pattern supports the motivation for typed repair policies: a local
repair may be competitive for a contained sign error, while global regeneration
was stronger on the observed algebraic-transformation cases. It is not yet a
general conclusion because the pilot has only seven detected errors and lacks
several taxonomy categories. Unobserved categories are not zero-success results.

## Next Technical Priority

Before claiming a repair advantage, the verifier training set needs reviewed
natural model errors from harder problems, including valid traces so that the
verifier can learn when not to repair. A repair candidate should also require an
independent acceptance check; the current learned detector alone permits harmful
regressions. The matched-budget global-regeneration comparison should then be
repeated on the same hard subset.
