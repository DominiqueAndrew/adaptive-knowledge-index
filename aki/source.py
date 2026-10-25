"""Deterministic, non-executing Python extraction and immutable source identity."""
from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def token_count(text: str) -> int:
    """Deterministic proxy; NOT a model tokenizer or ARB's canonical tokenizer."""
    return len(re.findall(r"\w+|[^\w\s]", text))


def snapshot_id(documents: dict[str, str]) -> str:
    return digest("\n".join(f"{p}\0{digest(t)}" for p, t in sorted(documents.items())))


def read_python_tree(root: Path) -> dict[str, str]:
    docs = {}
    for p in sorted(root.rglob("*.py")):
        if p.is_symlink() or any(x.startswith(".") for x in p.relative_to(root).parts):
            continue
        if p.stat().st_size <= 1_000_000:
            docs[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8", errors="replace")
    return docs


def module_name(path: str) -> str:
    p = path.removeprefix("src/").removesuffix(".py")
    return p.removesuffix("/__init__").replace("/", ".")


def is_test(path: str) -> bool:
    p = PurePosixPath(path)
    return "tests" in p.parts or p.name.startswith("test_") or p.name.endswith("_test.py")


@dataclass(frozen=True)
class Parsed:
    edges: frozenset[tuple[str, str]]
    symbols: tuple[tuple[str, str, int, int], ...]
    errors: tuple[str, ...]


def parse(documents: dict[str, str]) -> Parsed:
    modules = {module_name(p): p for p in sorted(documents) if p.endswith(".py")}
    edges, symbols, errors = set(), [], []
    for path, text in sorted(documents.items()):
        if not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError):
            errors.append(path)
            continue
        mod = module_name(path)
        package = mod.split(".") if path.endswith("/__init__.py") else mod.split(".")[:-1]
        for node in ast.walk(tree):
            names = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols.append((path, node.name, node.lineno, node.end_lineno or node.lineno))
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = package[:len(package) - node.level + 1] if node.level else []
                base = ".".join(prefix + ([node.module] if node.module else []))
                names = [base] + [f"{base}.{a.name}" if base else a.name for a in node.names]
            for name in names:
                # Longest resolvable local module; includes package initializers.
                parts = name.split(".")
                while parts:
                    target = modules.get(".".join(parts))
                    if target and target != path:
                        edges.add((path, target))
                    parts.pop()
    return Parsed(frozenset(edges), tuple(symbols), tuple(errors))
