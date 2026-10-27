"""Revision-scoped SQLite base store and exact reachability materializations."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from .source import digest, is_test, parse, source_lines, token_count, STATIC_IMPORTS, require_relation_semantics

EXTRACTOR = "python-ast-import-v4-explicit-static-semantics"


class StaleRevision(ValueError):
    pass


class Store:
    def __init__(self, path: str | Path, scope: str, refresh_mode: str = "incremental",
                 batch_writes: bool = True):
        if refresh_mode not in {"full", "incremental"}:
            raise ValueError(refresh_mode)
        self.refresh_mode, self.batch_writes = refresh_mode, batch_writes
        self.parse_cache = {}
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT);
        CREATE TABLE IF NOT EXISTS spans(id TEXT PRIMARY KEY, scope TEXT, revision TEXT,
          path TEXT,start INTEGER,end INTEGER,hash TEXT,text TEXT,provenance TEXT);
        CREATE TABLE IF NOT EXISTS active_spans(path TEXT,span_id TEXT PRIMARY KEY);
        CREATE INDEX IF NOT EXISTS active_spans_path ON active_spans(path);
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
        row = self.db.execute("SELECT v FROM meta WHERE k='extractor'").fetchone()
        self.extractor = row[0] if row else ""
        row = self.db.execute("SELECT v FROM meta WHERE k='dynamic_imports'").fetchone()
        self.dynamic_imports = json.loads(row[0]) if row else []
        self.documents: dict[str, str] = {}
        self.tokens = dict(self.db.execute("SELECT path,tokens FROM files"))

    def refresh(self, documents: dict[str, str], provenance: str = "provided snapshot",
                invalidation: str = "global") -> dict:
        """Atomic conservative refresh. Never trust a caller's commit label alone."""
        begin = time.perf_counter_ns()
        if invalidation not in {"global", "selective"}:
            raise ValueError(invalidation)
        hashes = {p: digest(t) for p, t in documents.items()}
        revision = digest("\n".join(f"{p}\0{h}" for p,h in sorted(hashes.items())))
        hash_end = time.perf_counter_ns()
        meta = dict(self.db.execute("SELECT k,v FROM meta"))
        old_count = self.db.execute("SELECT count(*) FROM mats").fetchone()[0]
        if revision == self.revision and meta.get("extractor") == EXTRACTOR:
            self.documents = dict(documents)
            self.extractor = EXTRACTOR
            return {"revision": revision, "files": len(documents),
                    "edges": self.db.execute("SELECT count(*) FROM edges").fetchone()[0],
                    "parse_errors": json.loads(meta.get("parse_errors", "[]")),
                    "relationship_scope": self.relationship_scope(),
                    "invalidated": 0, "retained": old_count, "noop": True,
                    "changed_files": 0, "parsed_files": 0, "reused_files": 0,
                    "spans_written": 0, "hash_ns": hash_end-begin,
                    "parse_ns": 0, "invalidation_ns": 0, "storage_update_ns": 0,
                    "store_refresh_ns": time.perf_counter_ns()-begin}
        # Reopening a store has no syntax cache, but source rows can still update incrementally.
        parsed = parse(documents, self.parse_cache if self.refresh_mode == "incremental" else None, hashes)
        parse_end = time.perf_counter_ns()
        old_hashes = dict(self.db.execute("SELECT path,hash FROM files"))
        changed = {p for p,h in hashes.items() if old_hashes.get(p) != h}
        removed = old_hashes.keys() - documents.keys()
        full = self.refresh_mode == "full" or meta.get("extractor") != EXTRACTOR
        updated = set(documents) if full else changed
        old_edges = set(self.db.execute("SELECT src,dst FROM edges"))
        changed_edges = old_edges.symmetric_difference(parsed.edges)
        changed_src = {a for a,b in changed_edges}
        changed_dst = {b for a,b in changed_edges}
        retained = set()
        if invalidation == "selective" and meta.get("extractor") == EXTRACTOR:
            for key, payload in self.db.execute("SELECT key,payload FROM mats"):
                root, direction = json.loads(key)
                footprint = set(json.loads(payload)) | {root}
                boundary = changed_src if direction == "forward" else changed_dst
                if not footprint.intersection(boundary | removed):
                    retained.add(key)
        invalidation_end = time.perf_counter_ns()
        token_sizes = dict(self.tokens)
        spans_written = 0
        with self.db:
            if full:
                for table in ("files", "edges", "symbols", "search", "edge_spans", "active_spans"):
                    self.db.execute(f"DELETE FROM {table}")
                token_sizes.clear()
            else:
                for path in sorted(updated | removed):
                    for table in ("files", "symbols", "search", "active_spans"):
                        self.db.execute(f"DELETE FROM {table} WHERE path=?", (path,))
                    token_sizes.pop(path, None)
                self.db.executemany("DELETE FROM edges WHERE src=? AND dst=?", old_edges - parsed.edges)
                # Evidence references may change even when the edge itself survives.
                self.db.execute("DELETE FROM edge_spans")
            for (key,) in self.db.execute("SELECT key FROM mats").fetchall():
                if key in retained:
                    self.db.execute("UPDATE mats SET revision=? WHERE key=?", (revision, key))
                else:
                    self.db.execute("DELETE FROM mats WHERE key=?", (key,))
            for path in sorted(updated):
                text = documents[path]
                file_hash = hashes[path]
                token_sizes[path] = token_count(text)
                self.db.execute("INSERT INTO files VALUES(?,?,?,?)", (path, file_hash, is_test(path), token_sizes[path]))
                self.db.execute("INSERT INTO search VALUES(?,?)", (path, text))
                lines = source_lines(text)
                for start in range(0, len(lines), 80):
                    chunk = "".join(lines[start:start + 80])
                    content_hash = digest(chunk)
                    identity = digest(json.dumps([self.scope, revision, path, start + 1, content_hash]))
                    self.db.execute("INSERT OR IGNORE INTO spans VALUES(?,?,?,?,?,?,?,?,?)",
                                    (identity, self.scope, revision, path, start + 1,
                                     min(start + 80, len(lines)), content_hash, chunk, provenance))
                    self.db.execute("INSERT INTO active_spans VALUES(?,?)", (path, identity))
                    spans_written += 1
            span_ids = {(p,(start-1)//80): identity for p,start,identity in self.db.execute(
                "SELECT a.path,s.start,s.id FROM active_spans a JOIN spans s ON a.span_id=s.id")}
            self.db.executemany("INSERT INTO edges VALUES(?,?)", sorted(parsed.edges if full else parsed.edges - old_edges))
            self.db.executemany("INSERT INTO symbols VALUES(?,?,?,?)", (s for s in parsed.symbols if s[0] in updated))
            self.db.executemany("INSERT INTO edge_spans VALUES(?,?,?,?,?)",
                ((src,dst,line,span_ids[src,(line-1)//80],EXTRACTOR) for src,dst,line in parsed.evidence))
            self.db.execute("INSERT OR REPLACE INTO meta VALUES('revision',?)", (revision,))
            self.db.execute("INSERT OR REPLACE INTO meta VALUES('extractor',?)", (EXTRACTOR,))
            self.db.execute("INSERT OR REPLACE INTO meta VALUES('parse_errors',?)", (json.dumps(parsed.errors),))
            self.db.execute("INSERT OR REPLACE INTO meta VALUES('dynamic_imports',?)", (json.dumps(parsed.dynamic_imports),))
        self.revision, self.documents = revision, dict(documents)
        self.extractor = EXTRACTOR
        self.dynamic_imports = list(parsed.dynamic_imports)
        self.tokens = token_sizes
        return {"revision": revision, "files": len(documents), "edges": len(parsed.edges),
                "parse_errors": list(parsed.errors), "relationship_scope": self.relationship_scope(), "invalidated": old_count-len(retained),
                "retained": len(retained), "noop": False, "changed_files": len(changed | removed),
                "parsed_files": parsed.parsed_files, "reused_files": parsed.reused_files,
                "spans_written": spans_written, "hash_ns": hash_end-begin,
                "parse_ns": parse_end-hash_end, "invalidation_ns": invalidation_end-parse_end,
                "storage_update_ns": time.perf_counter_ns()-invalidation_end,
                "store_refresh_ns": time.perf_counter_ns()-begin}

    def check(self, revision: str, scope: str | None = None):
        if self.extractor != EXTRACTOR:
            raise StaleRevision("extractor version changed or uninitialized; refresh before querying")
        if revision != self.revision or (scope is not None and scope != self.scope):
            raise StaleRevision("requested source revision or scope is not current; refresh required")

    def relationship_scope(self) -> dict:
        return {"relation_semantics": STATIC_IMPORTS, "runtime_complete": False,
                "known_dynamic_import_site_count": len(self.dynamic_imports)}

    def edge_evidence(self, src: str, dst: str, revision: str, *, relation_semantics=STATIC_IMPORTS) -> list[dict]:
        """Ground an edge in immutable current spans; existence is not task correctness."""
        self.check(revision)
        require_relation_semantics(relation_semantics)
        rows = self.db.execute("""SELECT e.line,e.extractor,s.id,s.path,s.start,s.end,s.hash,s.text,s.provenance
          FROM edge_spans e JOIN spans s ON s.id=e.span_id JOIN active_spans a ON a.span_id=s.id
          WHERE e.src=? AND e.dst=? AND s.scope=? ORDER BY e.line""",
          (src,dst,self.scope))
        names=("line","extractor","span_id","path","start","end","sha256","text","provenance")
        return [dict(zip(names,row)) | {"current_revision": revision} | self.relationship_scope() for row in rows]

    def closure(self, root: str, direction: str, *, relation_semantics=STATIC_IMPORTS) -> list[str]:
        self.check(self.revision)
        require_relation_semantics(relation_semantics)
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
        self.check(self.revision)
        row = self.db.execute("SELECT revision,payload FROM mats WHERE key=?", (key,)).fetchone()
        return json.loads(row[1]) if row and row[0] == self.revision else None

    def put(self, key: str, rows: list[str]) -> int:
        return self.install(key, rows, [])

    def install(self, key: str, rows: list[str], victims: list[str]) -> int:
        """One durable transaction for replacement; separate mode is a measured ablation."""
        payload = json.dumps(rows, separators=(",", ":"))
        size = len(payload.encode()) + len(key.encode()) + len(self.revision) + 32
        if not self.batch_writes:
            for victim in victims:
                self.remove(victim)
        with self.db:
            if self.batch_writes:
                self.db.executemany("DELETE FROM mats WHERE key=?", ((v,) for v in victims))
            self.db.execute("INSERT OR REPLACE INTO mats VALUES(?,?,?,?)", (key, self.revision, payload, size))
        return size

    def clear_materializations(self):
        # Policy cost/history state is session-local. Never adopt unaccounted rows.
        if self.db.execute("SELECT 1 FROM mats LIMIT 1").fetchone():
            with self.db:
                self.db.execute("DELETE FROM mats")

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
