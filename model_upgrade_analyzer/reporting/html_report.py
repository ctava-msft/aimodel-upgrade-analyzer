"""HTML report writer (Jinja2 template, self-contained)."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Template

from ..models.domain import AnalysisReport


_TEMPLATE = Template(
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Model Upgrade Analyzer Report</title>
<style>
 body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; color: #222; }
 h1, h2, h3 { color: #1a365d; }
 .meta { color: #555; font-size: .9rem; }
 .deployment { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
 .sev-critical { color: #b71c1c; font-weight: 700; }
 .sev-high { color: #d84315; font-weight: 700; }
 .sev-medium { color: #ef6c00; }
 .sev-low { color: #2e7d32; }
 .sev-info { color: #37474f; }
 code { background: #f4f4f4; padding: 1px 4px; border-radius: 3px; }
 table { border-collapse: collapse; width: 100%; margin: .5rem 0; }
 th, td { border: 1px solid #eee; padding: 4px 8px; text-align: left; font-size: .9rem; }
 th { background: #fafafa; }
 .pill { display:inline-block; padding: 2px 8px; border-radius: 12px; font-size:.8rem; background:#eee; }
</style>
</head>
<body>
<h1>Model Upgrade Analyzer Report</h1>
<p class="meta">
 Generated {{ report.generated_at }} &middot; repo <code>{{ report.repo_path }}</code> &middot;
 {{ report.deployments|length }} deployment(s), {{ report.code_references|length }} code refs,
 {{ report.prompt_observations|length }} prompt observations.
</p>

{% if report.deployments %}
<h2>Deployment Impact</h2>
{% for d in report.deployments %}
<section class="deployment">
 <h3>{{ d.deployment_name }} <span class="pill">{{ d.urgency.value }}</span></h3>
 <table>
  <tr><th>Current</th><td><code>{{ d.current_model or 'unknown' }}</code></td></tr>
  <tr><th>Target</th><td><code>{{ d.target_model or 'unknown' }}</code></td></tr>
  <tr><th>Deployment type</th><td>{{ d.deployment_type.value }}{% if d.capacity is not none %} (capacity={{ d.capacity }}){% endif %}</td></tr>
  <tr><th>Retirement</th><td>{{ d.retirement_date or 'n/a' }}</td></tr>
  <tr><th>Complexity</th><td>{{ d.migration_complexity }}</td></tr>
  {% if d.parameters_affected %}
  <tr><th>Parameters</th><td>{{ d.parameters_affected|join(', ') }}</td></tr>
  {% endif %}
 </table>

 {% if d.code_references %}
 <h4>Code references ({{ d.code_references|length }})</h4>
 <ul>
 {% for r in d.code_references[:25] %}
  <li><code>{{ r.file_path }}:{{ r.line }}</code> — {{ r.reference_kind }} = <code>{{ r.value }}</code></li>
 {% endfor %}
 </ul>
 {% endif %}

 {% if d.prompt_files %}
 <h4>Prompts</h4>
 <ul>{% for p in d.prompt_files %}<li><code>{{ p }}</code></li>{% endfor %}</ul>
 {% endif %}

 {% if d.recommended_validation %}
 <h4>Recommendations</h4>
 <ul>{% for r in d.recommended_validation %}<li>{{ r }}</li>{% endfor %}</ul>
 {% endif %}

 {% if d.findings %}
 <h4>Findings</h4>
 <ul>
 {% for f in d.findings %}
  <li class="sev-{{ f.severity.value }}">
   <strong>[{{ f.severity.value|upper }} / {{ f.confidence.value }}]</strong>
   {{ f.message }}
   {% if f.evidence %}
    <br><small>evidence:
    {% for e in f.evidence %}
     <code>{{ e.file_path }}{% if e.line %}:{{ e.line }}{% endif %}</code>{% if not loop.last %}, {% endif %}
    {% endfor %}
    </small>
   {% endif %}
   {% if f.recommendation %}<br><em>{{ f.recommendation }}</em>{% endif %}
  </li>
 {% endfor %}
 </ul>
 {% endif %}
</section>
{% endfor %}
{% endif %}

{% if report.findings %}
<h2>Global Findings</h2>
<ul>
{% for f in report.findings %}
 <li class="sev-{{ f.severity.value }}">
  <strong>[{{ f.severity.value|upper }} / {{ f.confidence.value }}]</strong>
  {{ f.message }}
  {% if f.evidence and f.evidence[0].file_path %}
   <br><small>evidence:
    <code>{{ f.evidence[0].file_path }}{% if f.evidence[0].line %}:{{ f.evidence[0].line }}{% endif %}</code>
   </small>
  {% endif %}
  {% if f.recommendation %}<br><em>{{ f.recommendation }}</em>{% endif %}
 </li>
{% endfor %}
</ul>
{% endif %}
</body>
</html>
"""
)


def write_html_report(report: AnalysisReport, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_TEMPLATE.render(report=report), encoding="utf-8")
    return out_path
