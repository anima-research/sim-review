#!/usr/bin/env python3
"""Refresh only the cross-judge report inside static/summary.json (build.py does the same as part of a full rebuild).

  python3 sim/scripts/crossjudge.py report && python3 sim/site/refresh_crossjudge.py && cd sim/site && railway up --ci
"""
import json
from pathlib import Path

SITE = Path(__file__).resolve().parent
report = (SITE.parent / "rank" / "crossjudge-report.md").read_text()
p = SITE / "static" / "summary.json"; S = json.loads(p.read_text())
S.setdefault("crossjudge", {})["report_md"] = report
p.write_text(json.dumps(S, ensure_ascii=False))
print(f"summary.json crossjudge.report_md refreshed ({len(report):,} chars)")
