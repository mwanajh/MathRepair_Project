# Model Comparison Protocol

This protocol compares `qwen2-math:1.5b` with another model without changing
the experiment.

## 1. Verify that the model is installed

```powershell
python ollama_status.py --require-model <model-name>
```

Do not continue if the command reports that the model is not installed.

The runner also performs this preflight check before a new run. To use the
runner for report tooling without Ollama, use `--aggregate-only`; do not disable
the check for a real experiment unless there is a specific reason.

## 2. Use the same dataset

The first comparison must use the expanded set:

```text
expanded_heldout_model_problems.csv
```

Do not change its rows, expected answers, or categories.

## 3. Use the same configuration

Baseline:

```powershell
python run_repeated_experiments.py `
  --problems expanded_heldout_model_problems.csv `
  --seeds 160500 180500 200500 `
  --samples-per-problem 1 `
  --temperature 1.4 `
  --model qwen2-math:1.5b `
  --model-repair-attempts 2
```

Candidate model:

```powershell
python run_repeated_experiments.py `
  --problems expanded_heldout_model_problems.csv `
  --seeds 160500 180500 200500 `
  --samples-per-problem 1 `
  --temperature 1.4 `
  --model <model-name> `
  --model-repair-attempts 2
```

A non-default model is written to an output folder containing its model slug,
so the baseline is not overwritten.

## 4. Compare reports

```powershell
python compare_model_reports.py `
  --baseline expanded_heldout_model_problems_repeated_experiments\aggregate_report.json `
  --candidate expanded_heldout_model_problems_repeated_experiments_<model-slug>\aggregate_report.json
```

The script rejects reports when the problem-set hash, temperature, samples per
problem, or run count do not match.

## Output-contract evidence

Freeze the existing model and parser-sensitivity runs without making new model
calls:

```powershell
python output_contract_evidence.py
```

This command records the exact Ollama tag and digest, prompt-contract version,
primary and normalized parser versions, raw response, generation failure, and
strict and normalized accuracy. It covers the 1.5B and 3B default runs plus both
the default and JSON-contract 7B runs.

The portable raw-response archive is `output_contract_raw_outputs.json`. Its
SHA-256 is stored in `output_contract_evidence.json`; per-seed source trace
hashes are also retained. This makes later output-contract analysis possible
even though the large local `seed_*` working directories are ignored by Git.

## 5. Metrics to report

- Baseline, global-regeneration, and local-repair answer accuracy
- Baseline, global-regeneration, and local-repair trace validity
- Paired local-minus-global difference within each model
- Candidate-minus-baseline difference for each strategy
- Additional model calls and tokens under the matched budget
- Failure counts and infrastructure retries
- Typed error counts, accepted repairs, and corrected wrong answers

## Interpretation

A higher candidate-model accuracy does not automatically mean that local repair
caused the improvement. Separate these questions:

1. Is the new model better than the previous model without repair?
2. Does local repair retain an advantage over global regeneration under the same
   model and matched budget?

Do not mix different problem sets or different seeds in one comparison. A new
model report should preserve the model name, dataset SHA-256, temperature,
samples per problem, and run count.

Parser-normalized accuracy is a sensitivity analysis, not a replacement for
the strict end-to-end result. Generation failures remain in both denominators.
