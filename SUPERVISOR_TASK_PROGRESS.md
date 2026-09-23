# MathRepair Supervisor Task Progress

Updated: 23 September 2026

This update records the seven methodology tasks requested after the earlier
progress report. It supersedes the earlier statements that the reasoning graph
was separate from the model pipeline, that no MATH-500 pilot existed, and that
the ablation structure had not been prepared.

| Task | Status | Evidence and current result |
|---|---|---|
| 1. Connect graph to model pipeline | Completed | Every model trace now uses the reasoning graph internally. Nodes record ID, subgoal/state, parents, model reasoning, verification, typed error, affected descendants, repair, repaired state, and final status. |
| 2. Hard benchmark pilot | Completed within requested scope | A deterministic 40-problem MATH-500 subset contains 17 level-4 and 23 level-5 problems across seven subjects. The text-mode smoke test processed 40/40; it is not yet an accuracy result. |
| 3. Freeze typed-error taxonomy | Completed | Eight error types have definitions, positive/negative examples, detection contracts, and repair actions in `ERROR_TAXONOMY.md`. |
| 4. Typed-verifier data pipeline | Completed within requested scope | The generator produced 48 examples, six per error type, with correct/corrupted traces, error location/type, corrected step, and preferred action. This is synthetic supervision, not a natural error-rate estimate. |
| 5. Matched-budget experiment | Completed | Across 36 runs and seven detected-error cases, global regeneration reached 88.9% answer accuracy; uniform and adaptive local repair reached 86.1%. The shared additional-token ceiling was about 5,800, with zero budget violations. |
| 6. Ablation table | Completed within requested scope | The requested six-row structure is frozen. As explicitly allowed, two rows are measured, Full MathRepair is a rule-based proxy, and three future cells remain unfilled. |
| 7. Preserve model/output-contract evidence | Completed | Four experiment configurations preserve exact model digests, prompt/parser versions, 432 raw-output records, failures, trace hashes, and normalized accuracy. No additional model optimization was performed. |

## Experimental Design Alignment

The report now separates two protocols that must not be pooled:

| Protocol | Design | Result role |
|---|---|---|
| Earlier expanded repeated-seed evaluation | 36 algebra problems, three seeds, 108 completed runs, and matched per-error repair budgets | Earlier evidence: local 100.0%, global 92.6% |
| Fresh Task 5 total-budget pilot | 36 initial runs, seven detected errors, and an approximately 5,800 additional-token ceiling shared by global, uniform-local, and adaptive-local strategies | Current compute-controlled pilot: global 88.9%, both local arms 86.1% |

The Task 1-7 methodology also records the graph node schema, MATH-500 pilot
selection, frozen taxonomy, typed-verifier supervision schema, ablation evidence
states, and versioned output-contract archive. The two performance protocols
answer different questions, so neither result replaces the other.

## Task 5 Matched-Budget Result

| Strategy | Answer accuracy | Valid-trace rate | Repair success | Average calls | Average tokens |
|---|---:|---:|---:|---:|---:|
| No repair | 86.1% | 80.6% | 0.0% | 1.00 | 624.1 |
| Global regeneration | 88.9% | 88.9% | 42.9% | 1.25 | 757.4 |
| Uniform local repair | 86.1% | 83.3% | 14.3% | 1.25 | 772.1 |
| Adaptive local repair | 86.1% | 86.1% | 28.6% | 1.17 | 721.5 |

This pilot does not show a local-repair accuracy advantage. Adaptive allocation
used fewer actual tokens and improved trace validity over uniform allocation,
but global regeneration was 2.8 percentage points more accurate. This result
must remain separate from the earlier expanded repeated-seed experiment, where
local repair reached 100.0% and global regeneration reached 92.6% under a
different matched per-error protocol.

## Task 6 Ablation Status

| Variant | Status | Answer accuracy | Valid-trace rate |
|---|---|---:|---:|
| Full MathRepair | Rule-based proxy | 86.1% | 86.1% |
| No graph | Planned | -- | -- |
| No typed error | Planned | -- | -- |
| No adaptive compute | Measured | 86.1% | 83.3% |
| Global regeneration instead of local repair | Measured | 88.9% | 88.9% |
| No symbolic tool | Blocked by learned verifier | -- | -- |

Only rows marked measured can support a current ablation claim. The reference
row is not the final Full MathRepair system until the learned verifier exists.

## Task 7 Output-Contract Evidence

| Model and prompt | Generation failures | Strict accuracy | Normalized accuracy |
|---|---:|---:|---:|
| qwen2-math:1.5b, default | 0/108 | 90.7% | 90.7% |
| qwen2.5:3b, default | 24/108 | 47.2% | 59.3% |
| qwen2-math:7b, default | 91/108 | 13.0% | 41.7% |
| qwen2-math:7b, JSON contract | 10/108 | 75.0% | 79.6% |

Normalized accuracy is a parser-only sensitivity result. It does not replace
strict end-to-end accuracy. The two 7B rows show directly that the output
contract materially changes pipeline success for the same model artifact.

## Explicitly Deferred Work

The following items were explicitly outside this week's completion scope:

- Training and calibrating the learned verifier. Task 4 required starting the
  data-generation pipeline, not completing large-model training.
- Running a full real-model MATH-500 accuracy evaluation. Task 2 required a
  difficult 30-50 problem pilot and pipeline-processing check.
- Filling every ablation cell. Task 6 explicitly allowed unfinished cells while
  requiring the table structure to be created now.

These are not incomplete Task 1-7 deliverables.

## Proposed Follow-Up Experiments

- Repeat the three-arm matched-budget comparison on the hard benchmark pilot
  and report paired uncertainty.
- Add natural model errors to the controlled verifier dataset before training.
- Keep prompt/parser sensitivity as supporting evidence rather than the primary
  contribution.

## Current Methodological Boundary

The project now has the proposal-level data structures, controlled typed-error
supervision, matched-budget comparison, ablation plan, and reproducibility
archive. The learned verifier is not yet trained, the MATH-500 pilot has not yet
received a full accuracy evaluation, and three planned ablation cells remain
unmeasured. These are the next research priorities; additional web-interface
work and model-specific prompt optimization are not priorities this week.

## Reproduce the Evidence

```powershell
python show_experiments.py
python generate_verifier_dataset.py --count-per-type 6 --seed 42
python matched_budget_experiment.py --reuse-global-results --reuse-local-results
python ablation_table.py
python output_contract_evidence.py
python -m unittest discover -q
```

Current automated verification: 129/129 tests passing.
