# Model Upgrade Analyzer

A Python tool that analyzes Azure AI / LLM model upgrades by combining Model IQ output, application source code, prompt files, and model lifecycle metadata to produce an evidence-based impact report.

## Features

- Ingests Model IQ exports (JSON, CSV, XLSX, YAML)
- Scans source code (Python, JS/TS, JSON, YAML, env, toml, ini, markdown) for:
  - Hard-coded model names and deployment IDs
  - Azure OpenAI / OpenAI SDK usage
  - Inference parameters (temperature, max_tokens, reasoning, structured output, streaming)
- Scans prompt files and embedded prompt strings for upgrade-sensitive patterns
- Ingests model cards / lifecycle metadata (markdown + YAML)
- Correlates deployments → code refs → prompts → config → model card guidance
- Deterministic risk scoring and recommendations
- Outputs JSON, Markdown, and HTML reports

## Install

```bash
pip install -e .
```

## Usage

```bash
model-upgrade-analyzer \
  --modeliq ./data/modeliq.csv \
  --repo ./my-app \
  --model-cards ./model-cards \
  --output ./reports \
  --format json,md,html
```

All paths are optional except `--repo`. If `--modeliq` is omitted, only code/prompt findings are reported.

## Architecture

See package layout under `model_upgrade_analyzer/`. Core principles:

- **Evidence-first**: every finding carries `evidence`, `confidence`, and `severity`.
- **Deterministic core**: no LLM required; LLM enrichment can be added later.
- **Modular**: ingest, scanners, analysis, and reporting are separable.

## Development

```bash
pip install -e ".[dev]"
pytest
```
