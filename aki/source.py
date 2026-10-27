"""Deterministic, non-executing Python extraction and immutable source identity."""
from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

STATIC_IMPORTS = 'python-static-imports-v1'


class UnsupportedRelations(ValueError):
    """Requested semantics cannot be established by this non-executing extractor."""


def require_relation_semantics(semantics):
    if semantics != STATIC_IMPORTS:
        raise UnsupportedRelations('only python-static-imports-v1 is supported; complete runtime dependencies cannot be certified')


def dynamic_import_sites(tree):
    """Diagnostic hints, NOT an exhaustive detector or a runtime edge resolver.

    Aliases/reassignments, import hooks, exec and arbitrary dispatch make a complete
    runtime graph unavailable. Even an empty result never certifies completeness.
    """
    modules={'importlib'};functions={'__import__'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            modules.update(a.asname or a.name for a in node.names if a.name=='importlib')
        elif isinstance(node,ast.ImportFrom) and node.module=='importlib':
            functions.update(a.asname or a.name for a in node.names if a.name=='import_module')
    sites=[]
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call):continue
        call=node.func
        if ((isinstance(call,ast.Name) and call.id in functions)
            or (isinstance(call,ast.Attribute) and call.attr=='import_module'
                and isinstance(call.value,ast.Name) and call.value.id in modules)):
            sites.append(node.lineno)
    return tuple(sorted(set(sites)))


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_lines(text: str) -> list[str]:
    """Python physical lines, preserving terminators and embedded Unicode separators."""
    return [line for line in re.findall(r"[^\r\n]*(?:\r\n|\r|\n|$)", text) if line]


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
            # Preserve exact UTF-8 bytes, including CRLF/CR, in canonical hashes.
            docs[p.relative_to(root).as_posix()] = p.read_bytes().decode("utf-8", errors="strict")
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
    evidence: tuple[tuple[str, str, int], ...]
    parsed_files: int = 0
    reused_files: int = 0
    dynamic_imports: tuple[tuple[str, int], ...] = ()


def parse(documents: dict[str, str], cache: dict | None = None,
          hashes: dict[str, str] | None = None) -> Parsed:
    """Cache syntax only. Resolve every import against the current module universe.

    A new file can resolve a formerly missing import in an unchanged file, so
    caching resolved edges by the importing file's hash alone would be unsafe.
    The optional cache is bounded to the current set of Python paths.
    """
    modules = {module_name(p): p for p in sorted(documents) if p.endswith(".py")}
    edges, symbols, errors, evidence, dynamic = set(), [], [], set(), []
    parsed_files = reused_files = 0
    if cache is not None:
        for path in set(cache) - documents.keys():
            del cache[path]
    for path, text in sorted(documents.items()):
        if not path.endswith(".py"):
            continue
        file_hash = hashes[path] if hashes is not None else digest(text)
        cached = cache.get(path) if cache is not None else None
        if cached is not None and len(cached)==5 and cached[0] == file_hash:
            _, declarations, imports, error, sites = cached
            reused_files += 1
        else:
            declarations, imports, error, sites = [], [], False, ()
            parsed_files += 1
            try:
                tree = ast.parse(text)
            except (SyntaxError, ValueError, RecursionError):
                error = True
            if not error:
                sites=dynamic_import_sites(tree)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        declarations.append((path, node.name, node.lineno, node.end_lineno or node.lineno))
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        imports.append((isinstance(node, ast.ImportFrom), getattr(node, "level", 0),
                                        getattr(node, "module", None), tuple(a.name for a in node.names),
                                        node.lineno, node.end_lineno or node.lineno))
            if cache is not None:
                cache[path] = (file_hash, declarations, imports, error, sites)
        if error:
            errors.append(path)
            continue
        symbols.extend(declarations)
        dynamic.extend((path,line) for line in sites)
        mod = module_name(path)
        package = mod.split(".") if path.endswith("/__init__.py") else mod.split(".")[:-1]
        for from_import, level, module, aliases, start, end in imports:
            names = aliases
            if from_import:
                prefix = package[:len(package) - level + 1] if level else []
                base = ".".join(prefix + ([module] if module else []))
                names = [base] + [f"{base}.{a}" if base else a for a in aliases]
            for name in names:
                # Longest resolvable local module; includes package initializers.
                parts = name.split(".")
                while parts:
                    target = modules.get(".".join(parts))
                    if target and target != path:
                        edges.add((path, target))
                        evidence.add((path, target, start))
                        # A multiline import can cross canonical 80-line spans.
                        # Link every intersected span, not just the statement start.
                        first_boundary = ((start - 1)//80 + 1)*80 + 1
                        for line in range(first_boundary, end+1, 80):
                            evidence.add((path, target, line))
                    parts.pop()
    return Parsed(frozenset(edges), tuple(symbols), tuple(errors), tuple(sorted(evidence)), parsed_files, reused_files, tuple(dynamic))
