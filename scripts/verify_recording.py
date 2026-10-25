#!/usr/bin/env python3
"""Validate one explicitly supplied local capture; no discovery or upload."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aki.recorder import verify
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
print(json.dumps(verify(a.directory),indent=2))
