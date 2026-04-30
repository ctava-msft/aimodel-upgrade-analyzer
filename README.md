---
title: Model Upgrade Analyzer
description: Evidence-based analysis of Azure AI / LLM model upgrades across deployments, code, prompts, and configuration.
author: Microsoft
ms.date: 2026-04-30
ms.topic: overview
keywords:
  - azure openai
  - model upgrade
  - model retirement
  - static analysis
estimated_reading_time: 8
---

## Overview

Model Upgrade Analyzer correlates Azure AI / Azure OpenAI deployment inventory with application source code, prompt assets, configuration files, and model lifecycle metadata to produce an evidence-based impact report. It answers a single question: *what breaks, regresses, or needs review when a deployed model is retired or upgraded?*

The toolkit ships three cooperating components:

| Component                             | Language   | Role                                                                                                        |
|---------------------------------------|------------|-------------------------------------------------------------------------------------------------------------|
| `Update-ModelRetirements.ps1`         | PowerShell | Builds and caches the model retirement lifecycle table (JSON/CSV).                                          |
| `Find-RetiringAzureAIDeployments.ps1` | PowerShell | Enumerates live Azure deployments and emits a Model IQ-shaped CSV of retiring models.                       |
| `model-upgrade-analyzer` (Python CLI) | Python     | Ingests the CSV plus your repository, performs correlation and risk scoring, writes JSON / Markdown / HTML. |

## Features

* Ingests Model IQ exports in JSON, CSV, XLSX, and YAML
* Scans source code (Python, JavaScript/TypeScript, JSON, YAML, `.env`, TOML, INI, Markdown) for:
  * Hard-coded model names and deployment IDs
  * Azure OpenAI / OpenAI SDK usage
  * Inference parameters (temperature, max_tokens, reasoning, structured output, streaming)
* Scans prompt files and embedded prompt strings for upgrade-sensitive patterns
* Ingests model cards and lifecycle metadata (Markdown + YAML)
* Correlates deployments to code references, prompts, configuration, and model-card guidance
* Deterministic risk scoring and prioritized recommendations
* Emits JSON, Markdown, HTML, and optional PPTX reports

## Install

```bash
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
pytest
```

The PowerShell scripts require `Az.Accounts` and `Az.Resources` (only when scanning live Azure):

```powershell
Install-Module Az.Accounts, Az.Resources -Scope CurrentUser
```

## End-to-End Workflow

The recommended flow runs the two PowerShell scripts first, then the Python analyzer.

```powershell
# 1. Build / refresh the retirement lifecycle table (cached at ./data/retirements.json).
./scripts/Update-ModelRetirements.ps1 -Refresh -AsCsv

# 2. Scan live Azure subscriptions and produce a Model IQ CSV of retiring deployments.
./scripts/Find-RetiringAzureAIDeployments.ps1 `
    -RetirementDataPath ./data/retirements.json `
    -OutputPath ./reports/modeliq.csv

# 3. Run the analyzer against your repository, fed by that CSV.
model-upgrade-analyzer `
    --repo . `
    --modeliq ./reports/modeliq.csv `
    --output ./reports `
    --format json,md,html
```

Data flow:

```text
Azure ARM (live)            ./data/retirements.json
        │                            │
        └────────────┬───────────────┘
                     ▼
   Find-RetiringAzureAIDeployments.ps1
                     │
                     ▼
            ./reports/modeliq.csv  ─────┐
                                        ▼
   repository source/prompts/configs ─► model-upgrade-analyzer ─► report.{json,md,html}
```

## Update-ModelRetirements.ps1

Builds the retirement lifecycle table consumed by the deployment scanner.

* Default output: `./data/retirements.json`
* Cache reuse: if the file exists and is younger than `-MaxAgeDays` (default 30), the script exits early and uses it
* Force rebuild: `-Refresh`
* Sources merged in precedence order (later overrides earlier on matching `model`):
  1. Built-in seed table inside the script
  2. Optional `-SourceUrl <https://…>` returning a JSON array
  3. Optional `-MergePath <local.json>` for organization-specific overrides
* `-AsCsv` also emits a sibling CSV with headers `model,retirement_date,replacement,notes`

```powershell
# Use cache if fresh; otherwise rebuild from seeds.
./scripts/Update-ModelRetirements.ps1

# Force rebuild and produce both JSON and CSV.
./scripts/Update-ModelRetirements.ps1 -Refresh -AsCsv

# Merge a remote feed plus a local override.
./scripts/Update-ModelRetirements.ps1 -Refresh `
    -SourceUrl 'https://example.com/retirements.json' `
    -MergePath ./data/retirements.local.json
```

## Find-RetiringAzureAIDeployments.ps1

Enumerates `Microsoft.CognitiveServices/accounts` of kind `OpenAI` or `AIServices` and their deployments, joins them against the retirement table, and writes a CSV that drops directly into the analyzer's `--modeliq` input.

* Inputs: live Azure (required) plus an optional `-RetirementDataPath` (JSON or CSV)
* Output columns map 1:1 to the Model IQ loader's field aliases (`deployment_name`, `current_model`, `current_version`, `recommended_replacement`, `retirement_date`, `region`, `subscription`, `sku`, `capacity`, `environment`, `urgency`, `deployment_type`, `notes`)
* `-DaysAhead` filters by the retirement window (default 365 days; `0` includes everything, including already-retired models)
* `-AsJson` additionally writes a JSON sibling

```powershell
# All accessible subscriptions, default 365-day window.
./scripts/Find-RetiringAzureAIDeployments.ps1

# Specific subscription, custom retirement table, custom output path.
./scripts/Find-RetiringAzureAIDeployments.ps1 `
    -SubscriptionId 'aaaa-bbbb' `
    -RetirementDataPath ./data/retirements.json `
    -OutputPath ./reports/modeliq.csv
```

## model-upgrade-analyzer (Python CLI)

```bash
model-upgrade-analyzer \
  --repo ./my-app \
  --modeliq ./reports/modeliq.csv \
  --model-cards ./model-cards \
  --output ./reports \
  --format json,md,html
```

| Flag            | Required | Purpose                                                                            |
|-----------------|----------|------------------------------------------------------------------------------------|
| `--repo`        | Yes      | Repository to analyze.                                                             |
| `--modeliq`     | No       | Model IQ export (JSON / CSV / XLSX / YAML). Without it, only code findings render. |
| `--model-cards` | No       | Directory or file with model cards (Markdown + YAML).                              |
| `--output`      | No       | Output directory (default `./reports`).                                            |
| `--format`      | No       | Comma-separated formats: `json`, `md`, `html`, `pptx` (default `json,md`).         |

## Architecture

The Python package lives under `model_upgrade_analyzer/`:

```text
model_upgrade_analyzer/
├── ingest/        # Model IQ + model card loaders, repo inventory
├── scanners/      # Code, prompt, config scanners; pattern library
├── analysis/      # Correlation, risk scoring, recommendations
├── reporting/     # JSON, Markdown, HTML, PPTX writers
├── models/        # Domain dataclasses
└── utils/         # Dates, files, logging, text helpers
```

Core principles:

* **Evidence-first.** Every finding carries `evidence`, `confidence`, and `severity`.
* **Deterministic core.** No LLM call required at runtime; LLM enrichment can be layered on later.
* **Modular.** Ingest, scanners, analysis, and reporting are independently testable and replaceable.

## Repository Layout

```text
.
├── data/                  # Cached retirement lifecycle data (generated)
├── model_upgrade_analyzer/
├── reports/               # Generated reports and Model IQ CSVs
├── scripts/
│   ├── Find-RetiringAzureAIDeployments.ps1
│   └── Update-ModelRetirements.ps1
├── tests/
├── pyproject.toml
└── SPEC.md
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

> [!NOTE]
> The seed retirement dates in `Update-ModelRetirements.ps1` are placeholders. Replace or override them with authoritative lifecycle data (via `-SourceUrl` or `-MergePath`) before treating output as ground truth.
