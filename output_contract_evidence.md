# Output-Contract Sensitivity Evidence

This archive freezes the prompt, parser, model artifact, raw outputs, generation failures, and normalized accuracy for the existing model runs. No new model inference is required.

| Model | Prompt version | Parser version | Runs | Raw outputs | Empty raw | Failures | Strict accuracy | Normalized accuracy | Delta |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| qwen2-math:1.5b | equation_json_default_v1 | equation_parser_default_v1 | 108 | 108 | 0 | 0 | 90.7% | 90.7% | +0.0 pp |
| qwen2.5:3b | equation_json_default_v1 | equation_parser_default_v1 | 108 | 108 | 0 | 24 | 47.2% | 59.3% | +12.0 pp |
| qwen2-math:7b | equation_json_default_v1 | equation_parser_default_v1 | 108 | 108 | 1 | 91 | 13.0% | 41.7% | +28.7 pp |
| qwen2-math:7b | equation_json_qwen2_v1 | equation_parser_qwen2_v1 | 108 | 108 | 0 | 10 | 75.0% | 79.6% | +4.6 pp |

## Interpretation

Normalized accuracy is a parser-only sensitivity result. It does not replace strict end-to-end accuracy or establish model superiority.

The default 7B run has one empty raw response; it is retained as an observed generation failure rather than silently removed.

The 7B rows use the same model artifact with two output contracts. This isolates prompt/parser-contract sensitivity more directly than comparing different model sizes.
