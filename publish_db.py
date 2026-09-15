#!/usr/bin/env python3
"""Publish sim/site/data.sqlite to R2 for the Railway deployment — incrementally when possible.

  python3 sim/site/publish_db.py        # after build.py; then `railway service restart --yes` (or `railway up --ci` if static changed)

Objects in bucket wfe:
  sim/data.sqlite.zst              full snapshot (zstd)                     — always uploaded (fallback for fresh volumes)
  sim/data.sqlite.zst.sha256       "<sha256 of uncompressed DB>  data.sqlite" — what entrypoint.sh compares against its local copy
  sim/data.sqlite.patch.zst        zstd --patch-from delta: previous published DB → this one (typically ~30 MB vs ~450 MB)
  sim/data.sqlite.patch.zst.from   sha256 of the DB the patch applies to
The previously published DB is kept in sim/site/.published/data.sqlite so the next run can diff against it.
Credentials are the R2 keys in scripts/upload_images_r2.py.
"""
import hashlib, importlib.util, os, shutil, subprocess, sys, tempfile
from pathlib import Path
import boto3
from boto3.s3.transfer import TransferConfig

SITE = Path(__file__).resolve().parent; DB = SITE / "data.sqlite"; PUB = SITE / ".published"; PREV = PUB / "data.sqlite"
KEY = "sim/data.sqlite.zst"; PATCH = "sim/data.sqlite.patch.zst"
class _R2:  # credentials: env vars R2_ENDPOINT / R2_ACCESS_KEY / R2_SECRET_KEY / R2_BUCKET, else the private wfe checkout's scripts/upload_images_r2.py
    ENDPOINT = os.environ.get("R2_ENDPOINT"); ACCESS_KEY = os.environ.get("R2_ACCESS_KEY"); SECRET_KEY = os.environ.get("R2_SECRET_KEY"); BUCKET = os.environ.get("R2_BUCKET", "wfe")
r2 = _R2()
if not (r2.ENDPOINT and r2.ACCESS_KEY and r2.SECRET_KEY):
    _p = SITE.parents[1] / "scripts" / "upload_images_r2.py"
    if not _p.exists(): sys.exit("set R2_ENDPOINT / R2_ACCESS_KEY / R2_SECRET_KEY (or run inside the wfe checkout)")
    spec = importlib.util.spec_from_file_location("r2", _p); r2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(r2)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""): h.update(chunk)
    return h.hexdigest()


sha = sha256(DB); print(f"sha256 {sha}  ({DB.stat().st_size/1e9:.2f} GB)")
prev_sha = sha256(PREV) if PREV.exists() else None
if prev_sha == sha: print("unchanged since last publish; nothing to do"); sys.exit(0)
s3 = boto3.client("s3", endpoint_url=r2.ENDPOINT, aws_access_key_id=r2.ACCESS_KEY, aws_secret_access_key=r2.SECRET_KEY, region_name="auto")
cfg = TransferConfig(multipart_chunksize=64 << 20, max_concurrency=8)
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    if prev_sha:
        patch = td / "patch.zst"
        subprocess.run(["zstd", "-T0", "-3", "-q", "-f", "--patch-from", str(PREV), str(DB), "-o", str(patch)], check=True)
        print(f"patch from {prev_sha[:12]}: {patch.stat().st_size/1e6:.0f} MB; uploading…")
        s3.upload_file(str(patch), r2.BUCKET, PATCH, Config=cfg, ExtraArgs={"ContentType": "application/zstd"})
        s3.put_object(Bucket=r2.BUCKET, Key=PATCH + ".from", Body=f"{prev_sha}\n".encode(), ContentType="text/plain")
    else:
        print("no previous published DB (sim/site/.published/); full snapshot only this time")
    zst = td / "data.sqlite.zst"
    subprocess.run(["zstd", "-T0", "-3", "-q", "-f", str(DB), "-o", str(zst)], check=True)
    print(f"full snapshot {zst.stat().st_size/1e6:.0f} MB; uploading…")
    s3.upload_file(str(zst), r2.BUCKET, KEY, Config=cfg, ExtraArgs={"ContentType": "application/zstd"})
    s3.put_object(Bucket=r2.BUCKET, Key=KEY + ".sha256", Body=f"{sha}  data.sqlite\n".encode(), ContentType="text/plain")   # last: flips the version only once everything else is in place
PUB.mkdir(exist_ok=True); shutil.copy2(DB, PREV)
print(f"published {sha[:12]} → https://pub-98e16b2a0fcf4d8286b5976e0b8720b9.r2.dev/{KEY}")
