"""Lightweight AST helpers for Python. Other languages fall back to regex."""
from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass
class KwargHit:
    """A keyword argument detected in a Python call."""

    call_name: str
    kwarg: str
    value: str
    line: int


def extract_python_call_kwargs(source: str, kwargs_of_interest: set[str]) -> list[KwargHit]:
    """Parse Python source and return keyword-argument assignments of interest.

    Returns hits for calls like `client.chat.completions.create(model="gpt-4o", temperature=0.2)`.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    hits: list[KwargHit] = []

    class _Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            call_name = _call_name(node)
            for kw in node.keywords:
                if kw.arg in kwargs_of_interest and kw.arg is not None:
                    value = _literal_repr(kw.value)
                    hits.append(KwargHit(call_name=call_name, kwarg=kw.arg, value=value, line=kw.value.lineno))
            self.generic_visit(node)

    _Visitor().visit(tree)
    return hits


def _call_name(node: ast.Call) -> str:
    def render(n: ast.AST) -> str:
        if isinstance(n, ast.Name):
            return n.id
        if isinstance(n, ast.Attribute):
            return f"{render(n.value)}.{n.attr}"
        return type(n).__name__

    return render(node.func)


def _literal_repr(node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        return repr(node.value)
    try:
        return ast.unparse(node)  # py3.9+
    except (AttributeError, ValueError):
        return type(node).__name__
