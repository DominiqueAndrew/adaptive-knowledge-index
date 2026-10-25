#!/usr/bin/env python3
"""Download two pinned public ARB subsets; verify hashes and safely extract data.

No installer, credential, or upstream executable is invoked. Requires existing
zstd. Source corpora retain upstream licenses and must stay outside this repo.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

REV="5901e1ee3aff048290db72edf9c63bc498b79ea3"
BUNDLES={
 "v2_trace2code":"19b252e8cfff42107fedc74005dbb6972f2970af33651ce0c1571546819e41c4",
 "v2_abstention":"bb358d6b65b7ef6aa36b417240cab4f2d51a8d69e699e573cf324ab339a5c1d8",
 "v2_code2test":"387cdfb25835b176ba27707d43dc31cae6b31514231923af237ad04deef19c0b",
}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--subsets",default="v2_trace2code,v2_abstention")
    args=p.parse_args()
    root=args.out.resolve()
    root.mkdir(parents=True,exist_ok=False)
    (root/"downloads").mkdir()
    for subset in args.subsets.split(","):
        expected=BUNDLES[subset]
        name=f"agent_retrieval_bench_{subset}.tar.zst"
        url=f"https://huggingface.co/datasets/eyuansu71/agent_retrieval_bench/resolve/{REV}/releases/{subset}/{name}"
        archive=root/"downloads"/name
        h=hashlib.sha256()
        with urllib.request.urlopen(url) as response,archive.open("wb") as out:
            while block:=response.read(1024*1024):
                h.update(block)
                out.write(block)
        if h.hexdigest()!=expected: raise ValueError("archive checksum mismatch")
        proc=subprocess.Popen(["zstd","-dc",str(archive)],stdout=subprocess.PIPE)
        with tarfile.open(fileobj=proc.stdout,mode="r|") as tar:
            for member in tar:
                path=Path(member.name)
                if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                    raise ValueError("unsafe archive member")
                if not member.isfile() or path.parts[0] not in {"corpus","benchmark"}: continue
                target=root/path
                target.parent.mkdir(parents=True,exist_ok=True)
                with tar.extractfile(member) as src,target.open("xb") as dst:
                    shutil.copyfileobj(src,dst)
        if proc.wait()!=0: raise RuntimeError("zstd failed")
        print(subset,expected,flush=True)


if __name__=="__main__": main()
