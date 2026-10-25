"""Revision-scoped SQLite base store and exact reachability materializations."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from .source import digest, is_test, parse, snapshot_id, token_count


class StaleRevision(ValueError):
    pass


class Store:
    def __init__(self, path: str | Path, scope: str):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT);
        CREATE TABLE IF NOT EXISTS spans(id TEXT PRIMARY KEY, scope TEXT, revision TEXT,
          path TEXT,start INTEGER,end INTEGER,hash TEXT,text TEXT,provenance TEXT);
        CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, hash TEXT,test INTEGER,tokens INTEGER);
        CREATE TABLE IF NOT EXISTS edges(src TEXT,dst TEXT,PRIMARY KEY(src,dst));
        CREATE INDEX IF NOT EXISTS edges_dst ON edges(dst,src);
        CREATE TABLE IF NOT EXISTS symbols(path TEXT,name TEXT,start INTEGER,end INTEGER);
        CREATE INDEX IF NOT EXISTS symbols_name ON symbols(name);
        CREATE TABLE IF NOT EXISTS edge_spans(src TEXT,dst TEXT,line INTEGER,span_id TEXT,
          extractor TEXT,PRIMARY KEY(src,dst,line));
        CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(path,text);
        CREATE TABLE IF NOT EXISTS mats(key TEXT PRIMARY KEY,revision TEXT,payload TEXT,bytes INTEGER);
        """)
        old = self.db.execute("SELECT v FROM meta WHERE k='scope'").fetchone()
        if old and old[0] != scope:
            self.db.close()
            raise ValueError("project scope mismatch")
        self.scope = scope
        self.db.execute("INSERT OR REPLACE INTO meta VALUES('scope',?)", (scope,))
        self.db.commit()
        row = self.db.execute("SELECT v FROM meta WHERE k='revision'").fetchone()
        self.revision = row[0] if row else ""
        self.documents: dict[str, str] = {}
        self.tokens = dict(self.db.execute("SELECT path,tokens FROM files"))

    def refresh(self, documents: dict[str, str], provenance: str = "provided snapshot",
                invalidation: str = "global") -> dict:
        """Atomic conservative refresh. Never trust a caller's commit label alone."""
        revision = snapshot_id(documents)
        parsed = parse(documents)
        if invalidation not in {"global", "selective"}:
            raise ValueError(invalidation)
        old_edges = set(self.db.execute("SELECT src,dst FROM edges"))
        changed_edges = old_edges.symmetric_difference(parsed.edges)
        changed_src = {a for a,b in changed_edges}
        changed_dst = {b for a,b in changed_edges}
        removed = {r[0] for r in self.db.execute("SELECT path FROM files")} - documents.keys()
        retained = set()
        if invalidation == "selective":
            for key, payload in self.db.execute("SELECT key,payload FROM mats"):
                root, direction = json.loads(key)
                footprint = set(json.loads(payload)) | {root}
                boundary = changed_src if direction == "forward" else changed_dst
                if not footprint.intersection(boundary | removed):
                    retained.add(key)
        old_count = self.db.execute("SELECT count(*) FROM mats").fetchone()[0]
        with self.db:
            for table in ("files", "edges", "symbols", "search", "edge_spans"):
                self.db.execute(f"DELETE FROM {table}")
            for (key,) in self.db.execute("SELECT key FROM mats").fetchall():
                if key in retained:
                    self.db.execute("UPDATE mats SET revision=? WHERE key=?", (revision, key))
                else:
                    self.db.execute("DELETE FROM mats WHERE key=?", (key,))
            span_ids = {}
            token_sizes = {}
            for path, text in sorted(documents.items()):
                file_hash = digest(text)
                token_sizes[path] = token_count(text)
                self.db.execute("INSERT INTO files VALUES(?,?,?,?)", (path, file_hash, is_test(path), token_sizes[path]))
                self.db.execute("INSERT INTO search VALUES(?,?)", (path, text))
                lines = text.splitlines(keepends=True)
                for start in range(0, len(lines), 80):
                    chunk = "".join(lines[start:start + 80])
                    content_hash = digest(chunk)
                    identity = digest(json.dumps([self.scope, revision, path, start + 1, content_hash]))
                    span_ids[path, start//80] = identity
                    self.db.execute("INSERT OR IGNORE INTO spans VALUES(?,?,?,?,?,?,?,?,?)",
                                    (identity, self.scope, revision, path, start + 1,
                                     min(start + 80, len(lines)), content_hash, chunk, provenance))
            self.db.executemany("INSERT INTO edges VALUES(?,?)", sorted(parsed.edges))
            self.db.executemany("INSERT INTO symbols VALUES(?,?,?,?)", parsed.symbols)
            self.db.executemany("INSERT INTO edge_spans VALUES(?,?,?,?,?)",
                ((src,dst,line,span_ids[src,(line-1)//80],"python-ast-import-v1") for src,dst,line in parsed.evidence))
            self.db.execute("INSERT OR REPLACE INTO meta VALUES('revision',?)", (revision,))
        self.revision, self.documents = revision, dict(documents)
        self.tokens = token_sizes
        return {"revision": revision, "files": len(documents), "edges": len(parsed.edges),
                "parse_errors": list(parsed.errors), "invalidated": old_count-len(retained),
                "retained": len(retained)}

    def check(self, revision: str, scope: str | None = None):
        if revision != self.revision or (scope is not None and scope != self.scope):
            raise StaleRevision("requested source revision or scope is not current; refresh required")

    def edge_evidence(self, src: str, dst: str, revision: str) -> list[dict]:
        """Ground an edge in immutable current spans; existence is not task correctness."""
        self.check(revision)
        rows = self.db.execute("""SELECT e.line,e.extractor,s.id,s.path,s.start,s.end,s.hash,s.text,s.provenance
          FROM edge_spans e JOIN spans s ON s.id=e.span_id
          WHERE e.src=? AND e.dst=? AND s.revision=? AND s.scope=? ORDER BY e.line""",
          (src,dst,revision,self.scope))
        names=("line","extractor","span_id","path","start","end","sha256","text","provenance")
        return [dict(zip(names,row)) for row in rows]

    def closure(self, root: str, direction: str) -> list[str]:
        if direction not in {"forward", "reverse"}:
            raise ValueError(direction)
        a, b = ("src", "dst") if direction == "forward" else ("dst", "src")
        # UNION deduplicates nodes: finite even for cycles. No depth truncation.
        return [r[0] for r in self.db.execute(f"""
          WITH RECURSIVE reach(path) AS (
            SELECT path FROM files WHERE path=?
            UNION SELECT e.{b} FROM edges e JOIN reach r ON e.{a}=r.path)
          SELECT path FROM reach WHERE path<>? ORDER BY path
        """, (root, root))]

    def get(self, key: str) -> list[str] | None:
        row = self.db.execute("SELECT revision,payload FROM mats WHERE key=?", (key,)).fetchone()
        return json.loads(row[1]) if row and row[0] == self.revision else None

    def put(self, key: str, rows: list[str]) -> int:
        payload = json.dumps(rows, separators=(",", ":"))
        size = len(payload.encode()) + len(key.encode()) + len(self.revision) + 32
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO mats VALUES(?,?,?,?)", (key, self.revision, payload, size))
        return size

    def remove(self, key: str):
        with self.db:
            self.db.execute("DELETE FROM mats WHERE key=?", (key,))

    def usage(self) -> int:
        return self.db.execute("SELECT coalesce(sum(bytes),0) FROM mats").fetchone()[0]

    def storage(self) -> dict:
        page = self.db.execute("PRAGMA page_size").fetchone()[0]
        pages = self.db.execute("PRAGMA page_count").fetchone()[0]
        free = self.db.execute("PRAGMA freelist_count").fetchone()[0]
        return {"db_allocated_bytes": page * pages, "db_live_page_bytes": page * (pages-free),
                "materialized_logical_bytes": self.usage()}

    def rank(self, root: str, rows: list[str], kind: str, text: str = "") -> list[str]:
        if kind not in {"dependencies", "ripple", "tests"}:
            raise ValueError(kind)
        terms = set(text.lower().split())
        selected = [p for p in rows if kind != "tests" or is_test(p)]
        # Semantics are identical on cache hit/miss; no stored answer or query text.
        return sorted(selected, key=lambda p: (-sum(t in p.lower() for t in terms), p))

    def pack(self, ranked: list[str], budget: int) -> list[str]:
        remaining, result = budget, []
        for path in ranked:
            cost = self.tokens.get(path)
            if cost is not None and cost <= remaining:
                result.append(path)
                remaining -= cost
        return result

    def close(self):
        self.db.close()
