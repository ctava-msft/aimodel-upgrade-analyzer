"""Regex pattern library for detecting model references and inference parameters."""
from __future__ import annotations

import re


# --- Model name patterns ---
# Order matters: more specific first. Each pattern captures the model name.
MODEL_NAME_PATTERNS: list[re.Pattern[str]] = [
    # OpenAI / Azure OpenAI family with versions
    re.compile(r"\b(gpt-4o(?:-mini)?(?:-\d{4}-\d{2}-\d{2})?)\b", re.IGNORECASE),
    re.compile(r"\b(gpt-4(?:\.\d+)?(?:-turbo)?(?:-\d{4}-\d{2}-\d{2})?)\b", re.IGNORECASE),
    re.compile(r"\b(gpt-4\.1(?:-mini|-nano)?)\b", re.IGNORECASE),
    re.compile(r"\b(gpt-5(?:-mini|-nano|-pro)?)\b", re.IGNORECASE),
    re.compile(r"\b(gpt-3\.5-turbo(?:-\d{4})?(?:-\d{2})?(?:k)?)\b", re.IGNORECASE),
    re.compile(r"\b(o1(?:-preview|-mini|-pro)?)\b", re.IGNORECASE),
    re.compile(r"\b(o3(?:-mini|-pro)?)\b", re.IGNORECASE),
    re.compile(r"\b(o4(?:-mini)?)\b", re.IGNORECASE),
    re.compile(r"\b(text-embedding-(?:ada-002|3-(?:small|large)))\b", re.IGNORECASE),
    re.compile(r"\b(dall-e-[23])\b", re.IGNORECASE),
    re.compile(r"\b(whisper-1)\b", re.IGNORECASE),
    # Anthropic
    re.compile(r"\b(claude-[0-9][a-z0-9.\-]*)\b", re.IGNORECASE),
    # Meta Llama
    re.compile(r"\b(llama-?[0-9][a-z0-9.\-]*)\b", re.IGNORECASE),
    # Mistral
    re.compile(r"\b(mistral-[a-z0-9.\-]+)\b", re.IGNORECASE),
    # Phi
    re.compile(r"\b(phi-[0-9](?:\.[0-9])?(?:-mini|-medium|-small)?)\b", re.IGNORECASE),
]


# --- Deployment / endpoint patterns ---
DEPLOYMENT_PATTERNS: list[re.Pattern[str]] = [
    # azure_deployment="..." / deployment_name="..." / deployment_id="..."
    re.compile(
        r"""(?P<key>azure_deployment|deployment_name|deployment_id|deploymentName)\s*[:=]\s*["']([^"']+)["']""",
        re.IGNORECASE,
    ),
    # model= or "model": style references with variable-looking values
    re.compile(r"""["']?(?:model|deployment)["']?\s*[:=]\s*["']([A-Za-z0-9][A-Za-z0-9._\-]{1,80})["']"""),
]


ENDPOINT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"""(?P<key>azure_endpoint|openai_endpoint|base_url|api_base|endpoint)\s*[:=]\s*["']([^"']+)["']""",
               re.IGNORECASE),
    re.compile(r"https://[A-Za-z0-9.\-]+\.openai\.azure\.com[/\w\-]*", re.IGNORECASE),
]


# --- SDK/client patterns ---
SDK_PATTERNS: dict[str, re.Pattern[str]] = {
    "azure_openai_python": re.compile(r"\b(AzureOpenAI|AsyncAzureOpenAI)\s*\(", re.IGNORECASE),
    "openai_python": re.compile(r"\b(OpenAI|AsyncOpenAI)\s*\("),
    "openai_legacy": re.compile(r"\bopenai\.(ChatCompletion|Completion|Embedding|Image|Audio)\b", re.IGNORECASE),
    "langchain_openai": re.compile(r"\b(AzureChatOpenAI|ChatOpenAI|AzureOpenAIEmbeddings|OpenAIEmbeddings)\s*\("),
    "semantic_kernel": re.compile(r"\b(AzureChatCompletion|AzureTextCompletion|AzureOpenAIChatCompletion)\b"),
    "agent_framework": re.compile(r"\b(AgentsClient|AgentBuilder|ChatAgent)\b"),
    "requests_to_openai": re.compile(r"requests\.(post|get)\(\s*[\"'][^\"']*openai[^\"']*[\"']", re.IGNORECASE),
}


# --- Inference parameters ---
PARAM_PATTERNS: dict[str, re.Pattern[str]] = {
    "temperature": re.compile(r"""["']?temperature["']?\s*[:=]\s*([0-9]*\.?[0-9]+)"""),
    "top_p": re.compile(r"""["']?top_?p["']?\s*[:=]\s*([0-9]*\.?[0-9]+)"""),
    "max_tokens": re.compile(r"""["']?max_(?:tokens|completion_tokens|output_tokens)["']?\s*[:=]\s*(\d+)"""),
    "reasoning_effort": re.compile(r"""["']?reasoning(?:_effort)?["']?\s*[:=]\s*["']?(low|medium|high|minimal)["']?""",
                                   re.IGNORECASE),
    "response_format_json": re.compile(r"""response_format\s*[:=]\s*\{[^}]*json""", re.IGNORECASE),
    "json_mode": re.compile(r"""json_?mode\s*[:=]\s*(True|true|["']?json_object["']?)"""),
    "stream": re.compile(r"""["']?stream["']?\s*[:=]\s*(True|true)"""),
    "tools": re.compile(r"""["']?tools["']?\s*[:=]\s*\["""),
    "function_call": re.compile(r"""function_call|tool_choice"""),
}


# --- Prompt traits ---
PROMPT_TRAIT_PATTERNS: dict[str, re.Pattern[str]] = {
    "strict_json": re.compile(
        r"(respond\s+only\s+in\s+json|output\s+only\s+valid\s+json|return\s+json|must\s+be\s+valid\s+json|"
        r"strictly\s+json)",
        re.IGNORECASE,
    ),
    "chain_of_thought": re.compile(
        r"(let'?s\s+think\s+step\s+by\s+step|think\s+step[- ]by[- ]step|show\s+your\s+(?:work|reasoning)|"
        r"chain[- ]of[- ]thought)",
        re.IGNORECASE,
    ),
    "few_shot": re.compile(r"(examples?:|few[- ]shot|example\s+\d+:|###\s*Example)", re.IGNORECASE),
    "model_specific_wording": re.compile(
        r"(as\s+an?\s+(?:gpt-?\d|gpt-?4|claude|llama)|you\s+are\s+(?:gpt|claude|llama))",
        re.IGNORECASE,
    ),
    "deprecated_model_reference": re.compile(
        r"\b(text-davinci-\d+|text-curie-\d+|code-davinci-\d+|gpt-3\.5-turbo-0301|gpt-4-0314)\b",
        re.IGNORECASE,
    ),
    "strong_formatting": re.compile(
        r"(respond\s+in\s+the\s+following\s+format|use\s+this\s+exact\s+format|output\s+format:|format\s+strictly)",
        re.IGNORECASE,
    ),
    "temperature_hint": re.compile(
        r"(set\s+temperature\s+to|with\s+temperature\s*=|at\s+temperature\s+0)", re.IGNORECASE
    ),
}


# Known deprecated models for quick checks in prompts/code.
DEPRECATED_MODELS = {
    "text-davinci-003",
    "text-davinci-002",
    "code-davinci-002",
    "gpt-3.5-turbo-0301",
    "gpt-4-0314",
    "gpt-4-0613",
}


def find_model_names(text: str) -> list[tuple[str, re.Match[str]]]:
    """Return (model_name, match) tuples across all patterns, de-duplicated by span."""
    seen: set[tuple[int, int]] = set()
    results: list[tuple[str, re.Match[str]]] = []
    for pat in MODEL_NAME_PATTERNS:
        for m in pat.finditer(text):
            span = m.span(1) if m.groups() else m.span()
            if span in seen:
                continue
            seen.add(span)
            results.append((m.group(1) if m.groups() else m.group(0), m))
    return results
