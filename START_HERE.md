# MathRepair: Start Here

## 1. What are we building?

MathRepair is a system that helps verify AI-generated mathematical reasoning
step by step. An AI model can produce an invalid intermediate step. MathRepair:

1. Receives a solution trace.
2. Verifies every step symbolically.
3. Identifies and classifies the first error.
4. Repairs the invalid step and verifies the final answer again.

This project does not build a new ChatGPT model from scratch. It uses an
existing model and focuses first on a transparent verifier and repair loop.

## 2. First example

Problem:

```text
2(x + 3) = 14
```

Correct distribution of 2:

```text
2x + 6 = 14
```

An AI model may produce:

```text
2x + 3 = 14
```

This is incorrect because `2 * 3` is `6`, not `3`.

## 3. Key terms

- **Model:** an AI system that generates solution steps.
- **Reasoning step:** one mathematical state, for example `2x + 3 = 14`.
- **Verifier:** a checker that tests whether a step is mathematically valid.
- **Error type:** a label such as `algebraic_transformation_error`.
- **Repair:** correcting an invalid step.
- **Local repair:** replacing only the invalid step instead of regenerating the
  entire solution.
- **Evaluation:** measuring whether the system detects and repairs errors
  correctly.

## 4. Run the first program

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

The program reports `ERROR FOUND`, the error type, the corrected step
`2x + 6 = 14`, and the correct solution `x = 4`.

The prototype currently checks arithmetic errors, sign errors, and simple
single-variable equations.

Evaluate the starter dataset with:

```powershell
python evaluate.py
```

The starter dataset contains 13 examples in `evaluation_data.csv`.

## 5. Verify multiple steps

Run:

```powershell
python reasoning_chain.py
```

Example:

```text
Original equation: 2(x + 3) = 14
Step 1: 2x + 3 = 14
Step 2: 2x = 11
Step 3: x = 5.5
Step 4:
```

Press Enter at the empty Step 4 prompt. The system identifies `n2` as the first
invalid node and marks `n3` and `n4` as affected.

## 6. Branching graph

Run:

```powershell
python reasoning_graph.py
```

The program reads `reasoning_graph_example.json`. The `n1 -> n2 -> n3` branch
contains an error, while the independent `n4 -> n5` branch is valid. Therefore,
the error in `n1` affects only `n2` and `n3`.

## 7. Repair policy

After detecting an error, the system selects an action based on the error type:

```text
arithmetic_error               -> TOOL_EXECUTE
sign_error                     -> BACKTRACK
algebraic_transformation_error -> REFORMALIZE
```

Run `python mathrepair_demo.py`, `python reasoning_chain.py`, or
`python reasoning_graph.py` to see the `Repair action` in the output.

## 8. Adaptive compute allocation

`python reasoning_graph.py` also prints a compute plan with a budget of 10
calls. Each node's priority is:

```text
uncertainty * importance * propagation risk
```

The error node and its descendants receive calls according to their priority.
The unaffected branch receives zero calls. These signals are currently
heuristic; a trained verifier can provide learned uncertainty later.

Save the compute plan as a research table:

```powershell
python allocation_report.py
```

## 9. Controlled synthetic data

Generate an 80-example dataset:

```powershell
python generate_dataset.py
python evaluate.py generated_evaluation_data.csv
```

The default seed is `42`, so rerunning the command produces the same dataset.
This makes the experiment reproducible.

## 10. Challenge set

Evaluate examples that were not produced by the generator:

```powershell
python evaluate.py challenge_evaluation_data.csv
```

This is a stronger test than the basic synthetic set because it contains new
equation structures. Use the `Full pass by category` section to find weak areas.

## 11. Model pipeline

Run the pipeline without installing a model:

```powershell
python model_pipeline.py --provider mock
```

The mock model deliberately produces an incorrect trace. MathRepair reports
the first error node, error type, repair action, affected nodes, and answer.

Save a trace for model-error analysis:

```powershell
python model_pipeline.py --provider mock --save-trace model_traces.jsonl
```

The local setup includes Ollama `0.34.1` and `qwen2-math:1.5b`. Run the real
model and save a trace with:

```powershell
python model_pipeline.py --provider ollama --model qwen2-math:1.5b --problem "2(x + 3) = 14" --save-trace natural_model_traces.jsonl
```

Model output may be prose or LaTeX. The adapter extracts equations while the
trace stores the raw response, extracted steps, token counts, and timings. The
same trace also contains the verified `reasoning_graph` used by the pipeline;
each node records its state, parent dependency, model reasoning, verification
result, error/impact fields, repair action, repaired state, and final status.

For the harder benchmark pilot, use the 40-problem MATH-500 subset:

```powershell
python benchmark_pilot.py --provider mock
```

It uses text-mode traces and labels them `text_unverified`; this is a pipeline
processing smoke test, not a symbolic-verifier result.

## 12. Batch model experiments

Start with three problems:

```powershell
python collect_model_traces.py --limit 3
```

The summary is written to `natural_model_report.json`, and raw traces are
written to `batch_model_traces.jsonl`.

Run the hard set:

```powershell
python collect_model_traces.py --problems hard_model_problems.csv --traces hard_model_traces.jsonl --report hard_model_report.json
```

Run multi-sampling for six problems with three samples each:

```powershell
python collect_model_traces.py --problems hard_model_problems.csv --limit 6 --samples-per-problem 3 --temperature 0.8 --seed 100 --traces multisample_traces.jsonl --report multisample_report.json
```

Run the high-temperature stress set:

```powershell
python collect_model_traces.py --problems stress_model_problems.csv --samples-per-problem 3 --temperature 1.4 --seed 500 --traces stress_multisample_traces.jsonl --report stress_multisample_report.json
```

The completed run produced `36/36` runs, `29/36` correct reasoning traces, and
`31/36` correct final answers before repair. Seven errors were detected and
symbolic local repair succeeded in `7/7` cases. The model generated repairs
without being given the answer; the verifier accepted `6/7`, corrected five
wrong answers without regressions, and reached `36/36` final-answer accuracy
with `35/36` valid traces. See `stress_multisample_report.json` for the full
breakdown.

Create compact research tables:

```powershell
python analyze_repair_experiment.py
```

Open `repair_experiment_summary.md` for the baseline, repair, and compute-cost
comparison.

Run the matched-budget baseline:

```powershell
python matched_budget_experiment.py
```

Pilot result: global regeneration reached `88.9%` answer accuracy, while local
repair reached `100%` under the same per-error token ceilings. This is still a
small 12-problem set, not a benchmark result.

Run the repeated-seed evaluation:

```powershell
python run_repeated_experiments.py
```

Five trials produced mean answer accuracy of `88.9%` for global regeneration and
`97.8%` for local repair. The local-minus-global difference was `+8.9`
percentage points, with a 95% Student-t interval of `[3.2, 14.6]`. This is a
preliminary result because all trials use the same 12 problems; the interval
measures seed variation only. The report is in
`repeated_experiments/aggregate_report.md`.

For generalization to problems not used in the stress set:

```powershell
python run_repeated_experiments.py --problems heldout_model_problems.csv --seeds 100500 120500 140500 --samples-per-problem 1 --temperature 1.4 --model-repair-attempts 2
```

The held-out experiment has 18 problems and three trials. Mean answer accuracy
was `96.3%` without repair, `98.1%` with global regeneration, and `100%` with
local repair; the paired 95% CI was `[-6.1%, 9.8%]`. Do not claim that local
repair is proven superior on this set. It is an initial generalization check
with substantial uncertainty.

The expanded 36-problem evaluation uses:

```powershell
python run_repeated_experiments.py --problems expanded_heldout_model_problems.csv --seeds 160500 180500 200500 --samples-per-problem 1 --temperature 1.4 --model-repair-attempts 2
```

Results were `90.7%` for no repair, `92.6%` for global regeneration, and
`100.0%` for local repair. The paired difference was `+7.4` percentage points,
with a 95% CI of `[3.4%, 11.4%]`. This is a larger evaluation set, but not an
official benchmark because it includes 18 earlier held-out problems and uses
the `qwen2-math:1.5b` model.

The stress, held-out, and expanded summaries are in
`RESEARCH_RESULTS_SUMMARY.md`. Ollama model status is in `MODEL_STATUS.md`.

## File guide

- `mathrepair_demo.py`: first interactive example
- `local_repair.py`: replaces an invalid step and verifies the new chain
- `model_repair.py`: generates repair candidates accepted or rejected by the verifier
- `analyze_repair_experiment.py`: creates research evaluation tables
- `matched_budget_experiment.py`: compares local and global regeneration
- `run_repeated_experiments.py`: repeats seeds and reports confidence intervals
- `README.md`: project overview and usage guide
- `START_HERE.md`: this step-by-step introduction

Next research steps are to add larger problem sets, use more seeds, and evaluate
larger models.
