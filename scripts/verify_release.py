#!/usr/bin/env python3
"""Verify the latest code/report/data fingerprints; old manifests need old checkout."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",type=Path,default=Path("docs/TASK420_ATTEMPT1_RELEASE.json"))
    args=p.parse_args()
    root=Path.cwd().resolve()
    manifest=json.loads(args.manifest.read_text())
    for name,expected in manifest["sha256"].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root): raise ValueError("manifest path escapes repository")
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=expected: raise ValueError(f"checksum mismatch: {name}")
    print(json.dumps({"passed":True,"verified_files":len(manifest["sha256"])}))


if __name__=="__main__":main()
