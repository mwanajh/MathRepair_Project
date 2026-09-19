# Model Status

The local Ollama installation contains three models:

| Model | Size | Quantization | Use |
|---|---:|---|---|
| `qwen2-math:1.5b` | 934,964,386 bytes | `Q4_0` | Current baseline |
| `qwen2.5:3b` | 1,929,912,432 bytes | `Q4_K_M` | Comparison candidate |
| `qwen2-math:7b` | 4,431,400,514 bytes | `Q4_0` | Larger math-model candidate |

Inspect installed models without the Ollama CLI:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags | ConvertTo-Json -Depth 5
```

Or use the project utility:

```powershell
python ollama_status.py
python ollama_status.py --require-model qwen2-math:1.5b
python ollama_status.py --require-model qwen2.5:3b
python ollama_status.py --require-model qwen2-math:7b
```

`qwen2.5:3b` and `qwen2-math:7b` were evaluated on the expanded set with
temperature `1.4`, seeds `160500 180500 200500`, and one sample per problem.
Candidate reports and model comparisons are stored in directories with the
`_qwen2.5_3b` and `_qwen2-math_7b` suffixes.

The repeated-experiment runner stores the model name in every trial and rejects
aggregation of reports from different models.

Non-default models also receive an output directory containing their model
slug, for example:

```text
expanded_heldout_model_problems_repeated_experiments_qwen2.5_3b
```

This prevents a new model experiment from overwriting baseline reports.

After installing a new model, compare reports with:

```powershell
python compare_model_reports.py --baseline <baseline-aggregate.json> --candidate <candidate-aggregate.json>
```

The complete comparison protocol is in `MODEL_COMPARISON_PROTOCOL.md`.

`run_repeated_experiments.py` performs a model preflight check before starting
new GPU runs. `--aggregate-only` does not wait for Ollama because it reads
existing reports only.
