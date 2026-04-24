# Model Upgrade Analyzer — Specification

You are helping build a Python-based analysis tool called **Model Upgrade Analyzer**.

## Goal

Build a Python tool that analyzes Azure AI / LLM model upgrades by combining:

1. **Model IQ output** (CSV, JSON, XLSX, or normalized export)
2. **Application source code**
3. **Prompt files**
4. **Model cards / lifecycle metadata**
5. **Optional deployment/config files**

The tool should identify:

- Which model upgrades are needed
- Which applications or code paths are affected
- What code/config/prompt changes may be required
- What validation and regression risks exist
- What observations should be surfaced for engineering and platform teams

The output should help engineering teams quickly understand:

- **upgrade urgency**
- **replacement model path**
- **compatibility considerations**
- **likely code changes**
- **prompt compatibility issues**
- **test recommendations**
- **operational follow-up items**

---

## Product framing

This tool is intended to support large-scale model lifecycle reviews where many deployments may be affected by retirements or upgrades. It should support a consolidated review model rather than forcing users to manually inspect one deployment at a time.

The tool should be opinionated but evidence-based:

- Always separate **facts found in files/code** from **inferred observations**
- Every observation should include supporting evidence when possible
- If evidence is weak or ambiguous, mark confidence as low

---

## Core capabilities

Implement the tool with these major capabilities:

### 1. Ingest Model IQ data

The tool must read structured Model IQ outputs from:

- `.json`
- `.csv`
- `.xlsx`
- normalized `.yaml` or `.yml`

Expected fields may include:

- deployment name
- current model
- current version
- recommended replacement
- retirement date
- region
- subscription
- SKU / offering
- environment
- urgency bucket
- **deployment type (PTU / provisioned vs. standard / pay-as-you-go vs. batch)**
- **capacity / PTU count (when applicable)**
- notes / advisory text

Normalize all input into a common internal model.

Deployment type classification must recognize at minimum:

- **PTU / provisioned**: `ProvisionedManaged`, `GlobalProvisionedManaged`, `DataZoneProvisionedManaged`, `PTU`
- **Standard / pay-as-you-go**: `Standard`, `GlobalStandard`, `DataZoneStandard`, `PayAsYouGo`
- **Batch**: `Batch`, `GlobalBatch`

When the Model IQ export does not carry an explicit deployment type, infer it from the
`sku` / `offering` field; when neither is present, infer from code/config evidence
(e.g. Bicep/ARM `sku: { name: 'ProvisionedManaged', capacity: 200 }`).

---

### 2. Scan repository source code

The tool must recursively scan source code and config files to detect:

- hard-coded model names
- deployment identifiers
- endpoint names
- Azure OpenAI / OpenAI API usage
- SDK client initialization
- inference parameters
- reasoning parameters
- max token settings
- structured output / JSON mode usage
- streaming usage
- retry / error handling tied to model behavior
- **deployment SKU / offering (PTU vs. Standard vs. Batch) in IaC files**
- **PTU capacity values (`capacity`, `ptu_count`, `sku.capacity`)**

Supported file types should include at minimum:

- `.py`
- `.js`
- `.ts`
- `.tsx`
- `.json`
- `.yaml`
- `.yml`
- `.env`
- `.toml`
- `.ini`
- `.bicep`
- `.tf`
- `.ipynb` (optional, stretch goal)
- `.md`

Use both:

- regex / pattern-based matching
- lightweight AST-based parsing where feasible

Do not rely only on exact string matches; support aliases, wrapper classes, and config indirection where possible.

---

### 3. Scan prompt files

The tool must read prompt files from common locations, such as:

- `/prompts`
- `/system-prompts`
- `/templates`
- `/instructions`
- `/chains`
- prompt strings embedded in code

Detect prompt characteristics that may be sensitive to model upgrades:

- strong formatting assumptions
- chain-of-thought / reasoning-specific prompting
- strict JSON output expectations
- model-specific prompt wording
- token-heavy prompts
- few-shot examples with brittle structure
- references to deprecated model names
- temperature/top_p assumptions
- vendor-specific phrasing

---

### 4. Read model cards / lifecycle metadata

The tool must ingest model cards or lifecycle metadata documents that describe:

- replacement models
- retirement dates
- modality changes
- context window differences
- input/output behavior changes
- feature support changes
- structured output compatibility
- reasoning model characteristics
- known migration guidance

If model cards are unstructured, extract useful metadata using rule-based parsing first.
Design the parser so an LLM-based summarization step could be added later, but keep the initial implementation deterministic.

---

### 5. Build upgrade impact mapping

The tool must correlate:

- Model IQ records
- code references
- prompt dependencies
- config references
- deployment names
- model card guidance

It should produce an impact map such as:

- **Deployment**
  - current model / target model
  - urgency
  - retirement date
  - **deployment type (PTU / Standard / Batch) and capacity**
  - source files referencing it
  - prompt files likely affected
  - parameters likely affected
  - estimated migration complexity
  - recommended validation steps

### 6. Deployment-type awareness (PTU vs. non-PTU)

The tool must differentiate between provisioned (PTU) and pay-as-you-go (Standard)
deployments and adjust findings and recommendations accordingly:

- PTU deployments raise a high-severity `ptu_deployment` finding and add capacity /
  region / blue-green cutover guidance to the recommendation set.
- PTU migrations add weight to the migration-complexity score.
- Standard deployments emit quota (TPM/RPM) and regional-availability guidance.
- Batch deployments emit batch-compatibility guidance.
- Deployment type and capacity are surfaced in JSON, Markdown, and HTML reports.

---

## Key design principles

### A. Evidence-first output

Every finding should carry:

- `finding_type`
- `severity`
- `confidence`
- `evidence`
- `recommendation`

Example:

- finding_type: `hardcoded_model_reference`
- severity: `high`
- confidence: `high`
- evidence: `src/app/inference.py:52 contains "gpt-4o"`
- recommendation: `replace config-driven or mapped model reference before migration`

### B. Separate fact from interpretation

Output should distinguish:

- **Observed facts**
- **Likely implications**
- **Suggested actions**

### C. Deterministic first

Start with deterministic, inspectable logic.
Do not require an LLM to produce baseline output.
If an LLM is added later, it should enrich observations, not replace core detection.

### D. Modular architecture

Use clean modules with testable boundaries.

---

## Recommended architecture

Implement the code using this structure:

```text
model_upgrade_analyzer/
  __init__.py
  cli.py
  config.py

  models/
    domain.py

  ingest/
    modeliq_loader.py
    model_card_loader.py
    repo_inventory.py

  scanners/
    code_scanner.py
    prompt_scanner.py
    config_scanner.py
    ast_helpers.py
    pattern_library.py
    deployment_type.py

  analysis/
    correlator.py
    upgrade_impact.py
    compatibility_rules.py
    risk_scoring.py
    recommendation_engine.py

  reporting/
    json_report.py
    markdown_report.py
    html_report.py
    pptx_export.py   # optional stretch goal

  utils/
    files.py
    logging.py
    dates.py
    text.py

tests/
  test_modeliq_loader.py
  test_code_scanner.py
  test_prompt_scanner.py
  test_correlator.py
  test_risk_scoring.py
  test_deployment_type.py
```
