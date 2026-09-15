#!/bin/sh
# Bring /data/data.sqlite up to the published version, then serve.
# DB_URL → full snapshot (zstd). Sidecars: DB_URL.sha256 (target sha of the uncompressed DB),
# ${DB_URL%.zst}.patch.zst + .from (zstd --patch-from delta and the sha it applies to). Patch when it matches
# the local copy (≈30 MB), else download the full snapshot (≈450 MB). Either way the result is sha-verified.
set -eu
DATA_DIR="${DATA_DIR:-/data}"; DB="$DATA_DIR/data.sqlite"; PATCH_URL="${DB_URL%.zst}.patch.zst"
mkdir -p "$DATA_DIR"
remote="$(curl -fsSL "$DB_URL.sha256" 2>/dev/null | cut -d' ' -f1 || true)"
local="$(cat "$DB.sha256" 2>/dev/null || true)"
if [ ! -s "$DB" ] && [ -z "$remote" ]; then echo "no local DB and cannot reach $DB_URL.sha256" >&2; exit 1; fi
if [ -s "$DB" ] && { [ -z "$remote" ] || [ "$remote" = "$local" ]; }; then
  echo "db up to date (sha256 $local)"
else
  rm -f "$DB.tmp"; ok=0
  if [ -s "$DB" ] && [ -n "$local" ]; then
    from="$(curl -fsSL "$PATCH_URL.from" 2>/dev/null | cut -d' ' -f1 || true)"
    if [ "$from" = "$local" ]; then
      echo "patching $local → $remote from $PATCH_URL"
      if curl -fsSL "$PATCH_URL" | zstd -d -q -f --long=31 --patch-from "$DB" -o "$DB.tmp" \
         && [ "$(sha256sum "$DB.tmp" | cut -d' ' -f1)" = "$remote" ]; then ok=1; else echo "patch failed or sha mismatch; falling back to full download" >&2; rm -f "$DB.tmp"; fi
    else
      echo "no patch from $local (patch base: ${from:-none}); full download"
    fi
  fi
  if [ "$ok" = 0 ]; then
    echo "fetching $DB_URL (sha256 $remote)"
    curl -fsSL "$DB_URL" | zstd -d -q -f -o "$DB.tmp"
    got="$(sha256sum "$DB.tmp" | cut -d' ' -f1)"
    if [ "$got" != "$remote" ]; then echo "downloaded snapshot sha $got != published $remote" >&2; rm -f "$DB.tmp"; exit 1; fi
  fi
  mv "$DB.tmp" "$DB"; printf '%s\n' "$remote" > "$DB.sha256"
  echo "db ready: $(du -h "$DB" | cut -f1) (sha256 $remote)"
fi
export SITE_DB="$DB"
exec python3 serve.py --host 0.0.0.0 --port "${PORT:-8787}"
