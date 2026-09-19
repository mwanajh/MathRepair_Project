# MathRepair Supervisor Demo

## Preparation

Open PowerShell and enter the project directory:

```powershell
cd C:\Users\mwana\Desktop\MathRepair_Project
```

This prototype runs with Python. PowerShell only starts the program; the
verifier and repair logic are implemented in Python files.

Run the complete demo with one command:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_supervisor_demo.ps1
```

The script uses the mock pipeline and saved reports; it does not rerun GPU
experiments.

## 1. Show error detection and symbolic repair

```powershell
python mathrepair_demo.py
```

Use this example:

```text
Original equation: 2(x + 3) = 14
Step to verify: 2x + 3 = 14
```

Explain that `2x + 3 = 14` is not equivalent to the original equation. The
system detects the distribution error, produces `2x + 6 = 14`, and obtains
`x = 4`.

## 2. Show the model-to-verifier pipeline

This demo does not use Ollama, so it is safe and fast:

```powershell
python model_pipeline.py --provider mock
```

The mock model deliberately produces an incorrect reasoning trace. MathRepair
shows the model steps, first error node, error type, repair action, affected
nodes, and correct answer.

## 3. Show the completed stress evaluation

Do not rerun the GPU experiment during the presentation. Build the summary
from the saved reports:

```powershell
python run_repeated_experiments.py --aggregate-only
```

Results from five seeds:

```text
No repair:       84.4% answer accuracy
Global repair:   88.9% answer accuracy
Local repair:    97.8% answer accuracy
```

Open the report:

```powershell
notepad .\repeated_experiments\aggregate_report.md
```

## 4. Show the held-out generalization check

The held-out set contains 18 new equations that were not used in the stress
set:

```powershell
python run_repeated_experiments.py --aggregate-only --problems heldout_model_problems.csv --seeds 100500 120500 140500 --samples-per-problem 1
```

Results:

```text
No repair:       96.3% answer accuracy
Global repair:   98.1% answer accuracy
Local repair:   100.0% answer accuracy
```

Open the report:

```powershell
notepad .\heldout_model_problems_repeated_experiments\aggregate_report.md
```

Do not claim that local repair is proven superior on the held-out set. The
paired 95% confidence interval for local-minus-global is `[-6.1%, 9.8%]`, so
this result is an initial generalization check.

To show results by mathematics topic:

```powershell
python category_analysis.py
python category_analysis.py --input-dir heldout_model_problems_repeated_experiments
notepad .\repeated_experiments\category_report.md
```

The stress report shows, for example, that nested distribution was difficult
for global regeneration while local repair recovered approximately `93.3%`
answer accuracy. Categories with few runs require cautious interpretation.

For the expanded 36-problem evaluation:

```powershell
python run_repeated_experiments.py --aggregate-only --problems expanded_heldout_model_problems.csv --seeds 160500 180500 200500 --samples-per-problem 1
notepad .\expanded_heldout_model_problems_repeated_experiments\aggregate_report.md
```

The saved results are `90.7%` for no repair, `92.6%` for global regeneration,
and `100.0%` for local repair. The local-versus-global difference is `+7.4`
percentage points, with a 95% CI of `[3.4%, 11.4%]`. Explain that 18 rows in
this dataset were inherited from the earlier held-out set and 18 rows are new.

To show typed error analysis for the expanded set:

```powershell
python error_analysis.py --input-dir expanded_heldout_model_problems_repeated_experiments
notepad .\expanded_heldout_model_problems_repeated_experiments\error_report.md
```

This set found 12 algebraic-transformation errors and 1 arithmetic error. All
13 repairs were accepted, 10 wrong answers were corrected, and no regressions
were observed.

To show adaptive compute allocation for the reasoning graph:

```powershell
python allocation_report.py
notepad .\allocation_report.md
```

Explain that the error node and its descendants receive extra calls while the
unaffected branch receives `0`. This is the proposal's heuristic based on
`uncertainty * importance * propagation risk`.

## Short explanation to say

> MathRepair does not accept a model answer by checking only the final answer.
> It verifies every reasoning step symbolically, identifies the first invalid
> step, and attempts to repair that local section. Local repair spends compute
> on the erroneous part instead of regenerating the entire solution.

## Prototype limitations

- It evaluates one-variable algebra equations, not all of mathematics.
- The model used is `qwen2-math:1.5b`.
- The problem sets are small and are not official benchmarks.
- The held-out confidence interval still has substantial uncertainty.
- The next step is to add independent datasets, larger models, and the full
  proposal-level adaptive graph repair.

## Do not do this during the demo

- Do not run `run_repeated_experiments.py` without `--aggregate-only`; it will
  start many model calls and may take a long time.
- Do not put an API key in a screenshot, terminal, README, or presentation.
- Do not mix `repeated_experiments` with
  `heldout_model_problems_repeated_experiments`; they are separate evaluations.
