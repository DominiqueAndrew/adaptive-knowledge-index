"""Evaluator-only checks against hand-authored import-edge fixtures, not parse().

This checks source grounding and declared edge expectations. It cannot certify
runtime Python behavior, dynamic imports, evidence sufficiency, or task success.
"""
import hashlib


def audit_evidence(store, documents, expected_edges):
    """expected_edges is an independently authored iterable of (src,dst,line)."""
    digest=lambda text:hashlib.sha256(text.encode('utf-8')).hexdigest()
    expected=set(expected_edges)
    actual=set(store.db.execute('SELECT src,dst FROM edges'))
    errors=[]
    if actual != {(src,dst) for src,dst,_ in expected}:
        errors.append('edge_set_mismatch')
    if dict(store.db.execute('SELECT path,hash FROM files')) != {p:digest(t) for p,t in documents.items()}:
        errors.append('source_hash_mismatch')
    for src,dst in sorted({(src,dst) for src,dst,_ in expected}):
        rows=store.edge_evidence(src,dst,store.revision)
        if {r['line'] for r in rows} != {line for a,b,line in expected if (a,b)==(src,dst)}:
            errors.append('edge_grounding_missing')
        for row in rows:
            # Fixtures use LF physical lines; no shared parser or span extraction.
            lines=documents[src].splitlines(keepends=True)
            text=''.join(lines[row['start']-1:row['end']])
            if (row['path']!=src or row['text']!=text or row['sha256']!=digest(text)
                or row['current_revision']!=store.revision or not row['start']<=row['line']<=row['end']):
                errors.append('stale_or_ungrounded_span')
    return {'passed':not errors,'errors':errors,'expected_edge_count':len(expected),
            'current_source_valid':not any(e in errors for e in ('source_hash_mismatch','stale_or_ungrounded_span')),
            'claim':'declared static import fixture only; not executable task correctness'}
