"""Opt-in evidence gate; a miss means insufficient routing evidence, not no answer."""
from collections import defaultdict
from pathlib import PurePosixPath
import re
from .source import digest


def mentioned(value: str, query: str) -> bool:
    return bool(re.search(r"(?<![\w/])" + re.escape(value) + r"(?![\w/])", query))


class EvidenceGate:
    def __init__(self, chunks: list[dict], generic_symbols: set[str]):
        self.paths = sorted({c["path"] for c in chunks if c.get("kind") == "file"})
        path_set = set(self.paths)
        basenames = defaultdict(set)
        symbols = defaultdict(dict)
        for path in self.paths:
            basenames[PurePosixPath(path).name].add(path)
        self.basenames = {name:next(iter(paths)) for name,paths in basenames.items() if len(paths) == 1}
        for c in chunks:
            symbol = str(c.get("symbol") or "").strip()
            if c.get("kind") != "symbol" or not symbol or symbol.lower() in generic_symbols or c.get("path") not in path_set:
                continue
            location = (c["path"], c.get("start_line"), c.get("end_line"))
            symbols[symbol][location] = {"kind":"symbol", "value":symbol, "path":c["path"],
                "start_line":c.get("start_line"), "end_line":c.get("end_line"),
                "source_sha256":digest(c.get("text", ""))}
        self.symbols = {s:next(iter(locations.values())) for s,locations in symbols.items() if len(locations) == 1}

    def check(self, query: str) -> dict:
        for path in self.paths:
            if mentioned(path, query):
                return {"allowed":True, "reason":"explicit_path", "path":path}
        for name,path in sorted(self.basenames.items()):
            if mentioned(name, query):
                return {"allowed":True, "reason":"unique_basename", "path":path}
        for symbol,evidence in sorted(self.symbols.items()):
            if mentioned(symbol, query):
                return {"allowed":True, "reason":"unique_symbol", "evidence":evidence}
        return {"allowed":False, "reason":"insufficient_evidence"}
