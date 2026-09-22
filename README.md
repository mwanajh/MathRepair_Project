# MathRepair Project

MathRepair is a prototype for verifying and repairing mathematical reasoning
traces. It checks intermediate equation states with a symbolic verifier,
localizes the first invalid step, and applies a targeted repair policy.

Thesis-ready results are consolidated in
[THESIS_RESULTS_CHAPTER.md](THESIS_RESULTS_CHAPTER.md). The document separates
the primary repair comparison, model/output-contract sensitivity, and residual
failure analysis.

The abstract, contributions, conclusion, and future-work draft are in
[THESIS_ABSTRACT_AND_CONCLUSION.md](THESIS_ABSTRACT_AND_CONCLUSION.md).
The defense brief and evidence-based questions are in
[DEFENSE_BRIEF.md](DEFENSE_BRIEF.md) and [DEFENSE_QA.md](DEFENSE_QA.md).

The pilot-to-proposal comparison is documented in
[PROPOSAL_ALIGNMENT_AUDIT.md](PROPOSAL_ALIGNMENT_AUDIT.md). The proposed-method
reasoning-graph demo is described in [PROPOSED_METHOD_DEMO.md](PROPOSED_METHOD_DEMO.md).
The artifact consistency audit is in
[research_artifact_audit.md](research_artifact_audit.md).

## Graphical web demo

Start the interactive web interface with:

```powershell
python graph_web_server.py --port 8765
```

Then open <http://127.0.0.1:8765/graph_demo.html>. Enter a problem equation
and one reasoning equation per line. The graph previews the submitted trace,
then the Python symbolic verifier marks clear, error, and affected nodes.

## Prototype workflow

This is an initial thesis prototype, not a new foundation model. It demonstrates
the central workflow on a small symbolic-algebra task:

1. The user enters an original equation.
2. The user enters the reasoning step to verify.
3. The verifier checks whether the equations have equivalent solution sets.
4. The system identifies arithmetic, sign, or algebraic errors.
5. The system returns a corrected step and the verified answer.

## Basic usage

Open PowerShell and run:

```powershell
cd C:\Users\mwana\Desktop\MathRepair_Project
python mathrepair_demo.py
```

Example input:

```text
Original equation: 2(x + 3) = 14
Step to verify: 2x + 3 = 14
```

## Dataset evaluation

`evaluation_data.csv` contains 13 starter examples. Run:

```powershell
python evaluate.py
```

The evaluator reports error-detection accuracy, error-type accuracy,
repair-action selection accuracy, and repair success rate.

## Targeted repair policy

`repair_policy.py` maps each diagnosed error type to an action:

- `arithmetic_error` -> `TOOL_EXECUTE`
- `sign_error` -> `BACKTRACK`
- `algebraic_transformation_error` -> `REFORMALIZE`
- `missing_assumption` -> `BACKTRACK`
- `logical_inference_error` -> `BACKTRACK`
- `semantic_interpretation_error` -> `REPLAN`
- `dependency_error` -> `BACKTRACK`
- `incomplete_solution` -> `REPLAN`
- unknown error -> `LOCAL_RESAMPLE`

The complete frozen contract, including definitions, examples, detection rules,
and secondary actions, is in [ERROR_TAXONOMY.md](ERROR_TAXONOMY.md) and the
machine-readable [error_taxonomy.py](error_taxonomy.py). A learned repair policy
must use these codes rather than introducing synonyms.

## Typed verifier pilot data

`generate_verifier_dataset.py` creates paired clean/corrupted reasoning graphs
for verifier supervision. Each record contains the correct trace, one controlled
corruption, error location/type, corrupted and correct states, dependency or
assumption metadata, and the preferred repair action. The checked-in pilot has
48 examples: six for each of the eight frozen reasoning-error types.

Regenerate it deterministically with:

```powershell
python generate_verifier_dataset.py --count-per-type 6 --seed 42
```

The dataset is intentionally controlled synthetic data for validating the label
contract. It is not yet a claim of natural model-error prevalence; later work
should add model-generated traces and independently reviewed labels.

## Adaptive compute allocation

`compute_allocator.py` uses the proposal heuristic:

```text
priority = uncertainty * structural importance * propagation risk
```

`reasoning_graph.py` assigns extra model calls to high-priority nodes. An
unaffected branch receives zero additional calls. This is a heuristic baseline;
learned verifier uncertainty can be added later.

Save the allocation plan as a research table with:

```powershell
python allocation_report.py
```

The report lists each node's signals and allocated extra calls.

## Synthetic dataset generation

Generate a reproducible dataset with 80 examples:

```powershell
python generate_dataset.py
python evaluate.py generated_evaluation_data.csv
```

The generator creates 20 examples for each group: correct, arithmetic error,
sign error, and algebraic-transformation error. Change the size or seed with:

```powershell
python generate_dataset.py --count-per-type 50 --seed 123
```

## Challenge evaluation

`challenge_evaluation_data.csv` is a hand-written test set that was not created
by the generator. It includes fractions, variables on both sides, negative
distribution, quadratics, identities, and equations without solutions.

```powershell
python evaluate.py challenge_evaluation_data.csv
```

The evaluator reports aggregate metrics and full-pass results by category.

## Model pipeline

Run the model-to-verifier pipeline without downloading a model:

```powershell
python model_pipeline.py --provider mock
```

The mock provider deliberately produces an error so that model output can be
checked by the reasoning graph, typed verifier, and repair policy. Save a trace:

```powershell
python model_pipeline.py --provider mock --save-trace model_traces.jsonl
```

`model_pipeline.py` also supports Ollama. After Ollama and a math model are
installed, run:

```powershell
python model_pipeline.py --provider ollama --model qwen2-math:1.5b --problem "2(x + 3) = 14" --save-trace natural_model_traces.jsonl
```

The local setup used for the experiments included Ollama `0.34.1`,
`qwen2-math:1.5b` (934 MB), `qwen2.5:3b` (1.93 GB), and `qwen2-math:7b`
(4.43 GB). The models ran on an RTX 2060 through the GPU. Ollama starts with
Windows; if the API is unavailable, launch Ollama from the Start menu.

See [MODEL_STATUS.md](MODEL_STATUS.md) for model status and inspection commands.
The 1.5B model is the baseline; the 3B and 7B models are comparison candidates.
Non-default models are written to model-specific output directories so they do
not overwrite baseline reports.

Check Ollama without the Ollama CLI:

```powershell
python ollama_status.py
```

The repeated-experiment runner checks that the requested model exists before a
new run. `--aggregate-only` reads saved reports without contacting Ollama.

## Model-specific output-contract experiment

The primary evaluation uses `--prompt-profile default` and remains unchanged.
For Qwen 7B, an optional profile requests JSON mode, plain-ASCII equations, and
a parser that discards explanatory entries inside the `steps` array:

```powershell
python run_repeated_experiments.py --model qwen2-math:7b `
  --prompt-profile qwen2_math_json `
  --problems expanded_heldout_model_problems.csv `
  --seeds 160500 180500 200500 `
  --samples-per-problem 1 `
  --temperature 1.4 `
  --output-dir expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b_prompt_json
```

Keep this profile's reports separate from the primary reports. Each trial stores
the prompt profile and model, and aggregation rejects mixed profiles. This is a
prompt/parser sensitivity experiment; it does not replace the primary result.

The current prototype expects one equation and model steps containing exactly
one `=` sign. This is a prototype limitation, not full competition-mathematics
support.

If a model does not return JSON, the adapter extracts equations from prose and
LaTeX. Each trace stores the raw response, extracted steps, diagnosis, token
counts, and generation timings for natural-error analysis. It also stores the
verified `reasoning_graph` used internally by MathRepair. Each graph node records
its `node_id`, `subgoal`, `reasoning_state`, `parent_dependency`,
`model_generated_reasoning`, `verification_result`, `error_type`,
`affected_descendants`, `repair_action`, `repaired_state`, and `final_status`.
The graph is therefore the pipeline's internal trace representation, not only a
web-demo rendering.

Run the supervisor demo using the mock pipeline and saved reports:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_supervisor_demo.ps1
```

Local generation uses temperature `0` and seed `42` for reproducibility. The
extractor removes coefficient symbols that do not occur in the problem, and the
answer metric selects the last step containing the problem variable.

The verifier distinguishes solution transformations from supporting identities.
Identities such as `45/5 = 9` or `6x - 15 + 4 = 6x - 11` are checked with SymPy
and accepted without requiring the identity's solution set to match the full
problem.

## Hard benchmark pilot

Task 2 uses a small, reproducible subset of [MATH-500](https://huggingface.co/datasets/HuggingFaceH4/MATH-500):
`math500_pilot_40.json` contains 40 level 4-5 problems stratified across all
seven subjects. `math500_pilot_40_manifest.json` records the selection rule,
source, subject/level counts, and file hash. The subset intentionally excludes
reference solutions so they are not exposed to the model.

Regenerate the subset from the public dataset-server API with:

```powershell
python prepare_math500_pilot.py
```

Run an offline pipeline smoke test across all 40 problems:

```powershell
python benchmark_pilot.py --provider mock
```

For a real model, use `--provider ollama --model <model-name>`. These problems
use the pipeline's text mode. Their reasoning graphs are recorded, but their
nodes are marked `verification_mode: text_unverified` until a domain-general
verifier is added; equation-mode symbolic metrics must not be mixed with this
pilot.

## Batch natural-model experiment

Start with three problems:

```powershell
python collect_model_traces.py --limit 3
```

Run all ten problems:

```powershell
python collect_model_traces.py
```

The problems are in `model_problems.csv`. Raw traces are written to
`batch_model_traces.jsonl`, and the summary is written to
`natural_model_report.json`.

Each new batch starts with a clean trace file by default. Use `--append` only
when intentionally adding runs to an existing trace file.

Run the 18-problem hard set with:

```powershell
python collect_model_traces.py --problems hard_model_problems.csv --traces hard_model_traces.jsonl --report hard_model_report.json
```

The report includes aggregate results, error-type counts, and category breakdowns.

Run stochastic multi-sampling with:

```powershell
python collect_model_traces.py --problems hard_model_problems.csv --limit 6 --samples-per-problem 3 --temperature 0.8 --seed 100 --traces multisample_traces.jsonl --report multisample_report.json
```

Each sample records its seed so the experiment is repeatable as far as the
backend allows. GPU generation can vary slightly even with the same seed. The
report shows sample-level accuracy and the number of unique symbolic answers
per problem.

Stress multi-sampling:

```powershell
python collect_model_traces.py --problems stress_model_problems.csv --samples-per-problem 3 --temperature 1.4 --seed 500 --traces stress_multisample_traces.jsonl --report stress_multisample_report.json
```

Current results for 12 problems and three samples per problem:

- completed runs: `36/36`
- correct reasoning traces before repair: `29/36`
- correct final answers before repair: `31/36`
- problems with mutually consistent samples: `10/12`
- detected errors: 5 algebraic, 1 sign, and 1 arithmetic
- automatic local repairs that passed verification: `7/7`
- model-generated repairs accepted by the verifier: `6/7`
- correct final answers after model repair: `36/36`
- valid reasoning traces after model repair: `35/36`
- wrong answers corrected: `5`; regressions: `0`
- model repair calls: `8` for 7 detected errors; tokens: `3,887`

The nested-distribution problem produced `x = 5` in all three samples even
though the correct answer is `x = 183/37`. This demonstrates that
self-consistency can strongly agree on an incorrect answer, while a symbolic
verifier can still detect it.

## Automatic local repair

`local_repair.py` preserves the verified reasoning prefix, replaces the first
invalid node, and removes affected downstream nodes. The new chain is checked
again; `success=True` is returned only after the second verification passes.

This is a symbolic-repair baseline: the verifier constructs the replacement and
correct answer.

## Model-generated local repair

`model_repair.py` gives the model the problem, verified prefix, first invalid
step, and error type. It does not provide the correct answer. A candidate is
accepted only if symbolic verification passes and it contains an isolated final
answer. If a model gives the correct answer and then adds an invalid step, the
verifier keeps the verified prefix and discards the invalid suffix.

If a candidate is correct but does not reach an isolated answer, the verified
partial repair is preserved. The next attempt continues from that equation
instead of restarting the entire solution.

Disable model repair or increase candidate attempts with:

```powershell
python collect_model_traces.py --model-repair-attempts 0
python collect_model_traces.py --model-repair-attempts 2
```

In the two-attempt run, one candidate required a verifier-feedback retry. One
repair was rejected, but its original final answer was already correct; this is
why accepted repairs were `6/7` while post-repair accuracy was `36/36`.

Create research tables for strategy comparison, repair success, token cost,
error types, and categories:

```powershell
python analyze_repair_experiment.py
```

Results are written to `repair_experiment_summary.json` and
`repair_experiment_summary.md`.

## Matched-budget comparison

Compare against verified global regeneration:

```powershell
python matched_budget_experiment.py
python analyze_repair_experiment.py
```

Under matched per-error total-token ceilings, the pilot produced:

- no repair: answer `86.1%`, valid traces `80.6%`
- verified global regeneration: answer `88.9%`, valid traces `88.9%`, 9 calls
- verified local repair: answer `100%`, valid traces `97.2%`, 8 calls

Global regeneration used `4,841/5,800` allowed tokens because accepted runs
stopped early and some remaining budgets could not fit another prompt. There
was no budget violation. These are results from a 12-problem pilot, not a
benchmark conclusion.

## Repeated-seed experiment

```powershell
python run_repeated_experiments.py
```

The runner uses base seeds `500`, `20500`, `40500`, `60500`, and `80500`.
Mean results were:

- no repair: answer `84.4%`, valid traces `82.8%`
- verified global regeneration: answer `88.9%`, valid traces `88.9%`
- verified local repair: answer `97.8%`, valid traces `97.2%`

The paired local-minus-global answer difference was `+8.9` percentage points,
with a 95% Student-t CI of `[3.2, 14.6]`. The interval excludes zero for these
five trials. This remains a preliminary result: every trial uses the same set
of 12 problems. The interval measures seed variation, not uncertainty from new
problem samples, so it is not a benchmark conclusion.

Rebuild aggregates without using the GPU:

```powershell
python run_repeated_experiments.py --aggregate-only
```

The aggregate table is in `repeated_experiments/aggregate_report.md`.
Add seeds without repeating completed trials:

```powershell
python run_repeated_experiments.py --resume
```

Run a new validated problem set:

```powershell
python run_repeated_experiments.py --problems heldout_model_problems.csv --seeds 100500 120500 140500 --samples-per-problem 1 --temperature 1.4 --model-repair-attempts 2
```

This held-out set contains 18 problems not used in the stress trials. With
three seeds, mean answer accuracy was `96.3%` without repair, `98.1%` with
verified global regeneration, and `100%` with verified local repair. The paired
local-minus-global CI was `[-6.1%, 9.8%]`, so this result does not demonstrate a
statistically conclusive advantage. Both strategies perform well on the new
set, which is still too small for a benchmark conclusion.

Create result tables by mathematical topic:

```powershell
python category_analysis.py
python category_analysis.py --input-dir heldout_model_problems_repeated_experiments
```

The tables are written to `category_report.md` inside each evaluation folder.
The stress category analysis shows nested distribution as a category where local
repair helped most, while many held-out categories already had high baseline
accuracy. Categories with few problems cannot support strong conclusions.

Summarize typed error outcomes with:

```powershell
python error_analysis.py --input-dir repeated_experiments
python error_analysis.py --input-dir expanded_heldout_model_problems_repeated_experiments
```

These reports show error types, detection counts, accepted repairs, corrected
wrong answers, and regressions.

For the larger 36-problem evaluation:

```powershell
python run_repeated_experiments.py --problems expanded_heldout_model_problems.csv --seeds 160500 180500 200500 --samples-per-problem 1 --temperature 1.4 --model-repair-attempts 2
```

The expanded evaluation completed `36/36` runs for each seed. Mean answer
accuracy was `90.7%` without repair, `92.6%` with global regeneration, and
`100.0%` with local repair. The paired local-minus-global difference was `+7.4`
percentage points with a 95% Student-t CI of `[3.4%, 11.4%]`. The dataset has
18 rows from the earlier held-out set and 18 new rows, so it is a larger
evaluation set but not a completely independent benchmark.

Reports are in
`expanded_heldout_model_problems_repeated_experiments/aggregate_report.md` and
`category_report.md`.

The consolidated results summary is in `RESEARCH_RESULTS_SUMMARY.md`.

## Model comparison and parser sensitivity

Model comparison requires matching problem sets, temperature, sample counts,
and run counts:

```powershell
python compare_model_reports.py --baseline <baseline-aggregate.json> --candidate <candidate-aggregate.json>
```

The script rejects different datasets or configurations so that model
comparisons do not contain avoidable confounders.

The current `qwen2.5:3b` comparison is in
`expanded_heldout_model_problems_repeated_experiments_qwen2.5_3b/model_comparison.md`.
The candidate was below the baseline in answer accuracy: `-43.5` pp without
repair, `-36.1` pp with global regeneration, and `-51.9` pp with local repair.
Generation failures `24/108` are included in the denominator.

Run offline parser sensitivity analysis without new model calls:

```powershell
python parser_sensitivity_analysis.py --input-dir expanded_heldout_model_problems_repeated_experiments_qwen2.5_3b
```

The analysis recovered all 24 raw outputs; 13 were correct and valid after
parser normalization. Candidate answer accuracy rose from `47.2%` to `59.3%`,
but the primary end-to-end comparison was not changed.

The `qwen2-math:7b` comparison is in
`expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b/model_comparison.md`.
Primary no-repair accuracy was `13.0%` versus the `90.7%` baseline, and
generation failures `91/108` remained in the denominator. Parser sensitivity
recovered `36/91` outputs and increased no-repair accuracy to `41.7%`; `55/91`
outputs could not be recovered. This is a sensitivity result separate from the
primary end-to-end comparison.

The full model-to-model comparison protocol is in
`MODEL_COMPARISON_PROTOCOL.md`.

Each aggregate stores the problem-set SHA-256, includes generation failures in
the denominator, rejects trials with missing runs, and rejects mixing reports
from different problem sets.

## Reasoning-chain verification

Verify multiple dependent steps with:

```powershell
python reasoning_chain.py
```

Enter the equation and its steps. Press Enter on an empty step when finished.
The program reports the first invalid node and affected downstream nodes.

## Branching reasoning graph

Run the example graph with:

```powershell
python reasoning_graph.py
```

The graph is stored in `reasoning_graph_example.json`. Each node has an `id`,
an equation in `text`, and parent node IDs in `depends_on`. When an error is
found, only descendants of that branch are marked as affected.

## Example equation

```text
2(x + 3) = 14
```

This example contains a distribution error: `2(x + 3)` should become
`2x + 6`, not `2x + 3`.

## File guide

- `mathrepair_demo.py`: first interactive prototype
- `evaluation_data.csv`: examples and expected outcomes
- `evaluate.py`: evaluates the system on a dataset
- `reasoning_chain.py`: verifies dependent reasoning nodes
- `reasoning_graph.py`: verifies a branching DAG and tracks descendants
- `reasoning_graph_example.json`: editable example graph
- `repair_policy.py`: selects a targeted repair action by error type
- `local_repair.py`: applies a repair, removes affected suffixes, and rechecks
- `model_repair.py`: generates local candidates and accepts only verified repairs
- `analyze_repair_experiment.py`: creates research metrics and tables
- `matched_budget_experiment.py`: compares local and global repair budgets
- `run_repeated_experiments.py`: runs multiple seeds and confidence intervals
- `compute_allocator.py`: assigns test-time compute to important nodes
- `generate_dataset.py`: creates controlled synthetic error data
- `challenge_evaluation_data.csv`: unseen hand-written challenge examples
- `model_pipeline.py`: connects model output to the MathRepair verifier
- `model_problems.csv`: problems for the batch natural-model experiment
- `hard_model_problems.csv`: nested, fractional, rational, and polynomial problems
- `stress_model_problems.csv`: large coefficients, rational equations, and cubics
- `collect_model_traces.py`: runs a model, stores traces, and writes a report
- `graph_demo.html`: graphical reasoning-graph interface
- `graph_web_server.py`: local web server and analysis API
- `README.md`: project usage and implementation guide

The next research stage is to add larger models, independent datasets, a
learned verifier, and the full proposal-level adaptive reasoning graph.
