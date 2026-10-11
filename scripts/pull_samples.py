#!/usr/bin/env python3
"""Validate inventory/sources/*.yaml and pull small samples from bulk/api sources.

Usage:
    python3 scripts/pull_samples.py --validate          # schema check only
    python3 scripts/pull_samples.py [--limit 100] [--only SOURCE_ID ...]

For each entry with access_type bulk|api and a non-null endpoint_url, fetches up
to --limit rows and writes samples/<source_id>/sample.{json,csv} and schema.json
(fields, inferred types, row count when reported, retrieved_at, sha256).
Failures are reported, never hidden; exit status is non-zero if any fail.
"""
import argparse
import csv
import hashlib
import io
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "inventory" / "sources"
SAMPLES = ROOT / "samples"

SECTIONS = {
    "identity", "assessment", "tax", "delinquency_tax_sale", "special_assessment",
    "ownership", "transfer", "deed_reference", "permit", "license",
    "inspection_enforcement", "building", "land",
}
ACCESS_TYPES = {"bulk", "api", "portal_search", "request_only", "paid"}
# How a portal_search source can be collected in practice (see inventory/lookup_alternatives.md).
COLLECTION = {"bulk_alternative", "scrape_feasible", "robots_disallowed", "blocked", "request_only"}
REQUIRED = [
    "source_id", "jurisdiction", "custodian", "dataset_name", "quoin_sections",
    "access_type", "landing_url",
]
JURISDICTIONS = {
    "arlington", "falls_church", "fairfax_county", "fairfax_city", "alexandria",
    "loudoun", "virginia_state", "regional",
}
UA = "nova-data-inventory/0.1 (+https://github.com/donna49/nova-data)"


def load_sources():
    sources = []
    for path in sorted(SOURCES_DIR.glob("*.yaml")):
        with path.open() as f:
            sources.extend(yaml.safe_load(f) or [])
    return sources


def validate(sources):
    errors, seen = [], set()
    for i, s in enumerate(sources):
        sid = s.get("source_id", f"<entry {i}>")
        for key in REQUIRED:
            if not s.get(key):
                errors.append(f"{sid}: missing {key}")
        if sid in seen:
            errors.append(f"{sid}: duplicate source_id")
        seen.add(sid)
        if s.get("jurisdiction") not in JURISDICTIONS:
            errors.append(f"{sid}: unknown jurisdiction {s.get('jurisdiction')!r}")
        if s.get("access_type") not in ACCESS_TYPES:
            errors.append(f"{sid}: invalid access_type {s.get('access_type')!r}")
        if s.get("collection") and s["collection"] not in COLLECTION:
            errors.append(f"{sid}: invalid collection {s['collection']!r}")
        bad_covers = set(s.get("covers") or []) - JURISDICTIONS
        if bad_covers:
            errors.append(f"{sid}: unknown covers {sorted(bad_covers)}")
        bad = set(s.get("quoin_sections") or []) - SECTIONS
        if bad:
            errors.append(f"{sid}: unknown sections {sorted(bad)}")
    return errors


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read()


def infer_type(values):
    vals = [v for v in values if v not in (None, "")]
    if not vals:
        return "null"
    if all(isinstance(v, bool) for v in vals):
        return "boolean"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in vals):
        return "integer"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
        return "number"
    return "string"


def sample_arcgis(url, limit):
    base = url.split("?")[0].rstrip("/")
    if base.endswith("/query"):
        base = base[: -len("/query")]
    q = {"where": "1=1", "outFields": "*", "returnGeometry": "false", "f": "json"}
    _, _, body = fetch(f"{base}/query?" + urllib.parse.urlencode({**q, "resultRecordCount": limit}))
    data = json.loads(body)
    if "error" in data:
        raise RuntimeError(f"ArcGIS error: {data['error']}")
    rows = [feat.get("attributes", {}) for feat in data.get("features", [])]
    count = None
    try:
        _, _, cbody = fetch(f"{base}/query?" + urllib.parse.urlencode({**q, "returnCountOnly": "true"}))
        count = json.loads(cbody).get("count")
    except Exception:  # count is best-effort
        pass
    return rows, count, "json"


def sample_socrata(url, limit):
    sep = "&" if "?" in url else "?"
    _, _, body = fetch(f"{url}{sep}$limit={limit}")
    return json.loads(body), None, "json"


def sample_odata(url, limit):
    sep = "&" if "?" in url else "?"
    _, _, body = fetch(f"{url}{sep}$top={limit}")
    data = json.loads(body)
    if isinstance(data, dict):
        data = data.get("value", data)
    return data, None, "json"


def sample_generic(url, limit):
    _, ctype, body = fetch(url)
    text = body.decode("utf-8-sig", errors="replace")
    if "json" in ctype or text.lstrip()[:1] in "[{":
        data = json.loads(text)
        if isinstance(data, dict):
            data = next((v for v in data.values() if isinstance(v, list)), [data])
        return data[:limit], len(data), "json"
    rows = list(csv.DictReader(io.StringIO(text)))
    return rows[:limit], len(rows), "csv"


def pull(source, limit):
    url = source["endpoint_url"]
    if "/FeatureServer/" in url or "/MapServer/" in url:
        rows, count, kind = sample_arcgis(url, limit)
    elif "datahub-v2.arlingtonva.us/api/" in url:
        rows, count, kind = sample_odata(url, limit)
    elif "/resource/" in url and url.split("?")[0].endswith(".json"):
        rows, count, kind = sample_socrata(url, limit)
    else:
        rows, count, kind = sample_generic(url, limit)
    if not rows:
        raise RuntimeError("endpoint returned 0 rows")

    out = SAMPLES / source["source_id"]
    out.mkdir(parents=True, exist_ok=True)
    if kind == "csv":
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        payload = buf.getvalue()
    else:
        payload = json.dumps(rows, indent=2, default=str)
    (out / f"sample.{kind}").write_text(payload)

    fields = {}
    for row in rows:
        for k in row:
            fields.setdefault(k, [])
    for k in fields:
        fields[k] = infer_type([r.get(k) for r in rows])
    schema = {
        "source_id": source["source_id"],
        "endpoint_url": url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sample_rows": len(rows),
        "reported_row_count": count,
        "sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "fields": fields,
    }
    (out / "schema.json").write_text(json.dumps(schema, indent=2) + "\n")
    return len(rows), count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()

    sources = load_sources()
    errors = validate(sources)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"OK: {len(sources)} entries valid")
    if args.validate:
        return 0

    targets = [
        s for s in sources
        if s["access_type"] in ("bulk", "api") and s.get("endpoint_url")
        and "pdf" not in (s.get("format") or "").lower()
        and (not args.only or s["source_id"] in args.only)
    ]
    failures = []
    for s in targets:
        try:
            n, count = pull(s, args.limit)
            print(f"PASS {s['source_id']}: {n} rows (reported total: {count})")
        except Exception as e:  # report every failure
            failures.append(s["source_id"])
            print(f"FAIL {s['source_id']}: {type(e).__name__}: {e}")
    print(f"\n{len(targets) - len(failures)}/{len(targets)} sources sampled")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
