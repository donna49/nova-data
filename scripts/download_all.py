#!/usr/bin/env python3
"""Download every free bulk/API source in inventory/sources/*.yaml, in full.

Usage:
    python3 scripts/download_all.py --list                 # show what would be downloaded
    python3 scripts/download_all.py                        # download everything into ./data
    python3 scripts/download_all.py --out /path/to/data
    python3 scripts/download_all.py --only SOURCE_ID ...   # specific sources
    python3 scripts/download_all.py --jurisdiction loudoun
    python3 scripts/download_all.py --force                # re-download completed sources

Output layout (see AGENTS.md for the full contract):
    <out>/<jurisdiction>/<source_id>/<data files>
    <out>/<jurisdiction>/<source_id>/_source.json   provenance: official source name, counts, hashes
    <out>/manifest.csv                              one row per source, rebuilt after every run

Provenance records the official office/department (`official_source`), not URLs.
Sources marked blocked, robots_disallowed, request_only, paid or portal_search are never fetched.
"""
import argparse
import csv
import hashlib
import http.cookiejar
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pull_samples import ROOT, UA, load_sources, validate

DOWNLOADABLE = {"bulk", "api"}
NEVER_FETCH = {"blocked", "robots_disallowed", "request_only"}
ODATA_PAGE = 10_000
RETRIES = 4

COOKIES = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(COOKIES))
DELAY = 0.3


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def request(url, data=None, timeout=180):
    """Open a URL with retries and exponential backoff; returns the response object."""
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
    for attempt in range(RETRIES):
        try:
            time.sleep(DELAY)
            return OPENER.open(req, timeout=timeout)
        except Exception:
            if attempt == RETRIES - 1:
                raise
            time.sleep(2 ** (attempt + 1))


def get_json(url, data=None):
    with request(url, data) as resp:
        payload = json.loads(resp.read())
    if isinstance(payload, dict) and "error" in payload:
        raise RuntimeError(f"service error: {payload['error']}")
    return payload


def save_stream(url, dest):
    """Stream a URL to dest; returns the filename suggested by the server, if any."""
    with request(url) as resp:
        disp = resp.headers.get("Content-Disposition", "")
        ctype = resp.headers.get("Content-Type", "")
        if "text/html" in ctype and not url.lower().endswith((".htm", ".html")):
            raise RuntimeError(f"expected a file but got an HTML page ({ctype})")
        with open(dest, "wb") as f:
            while chunk := resp.read(1 << 20):
                f.write(chunk)
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', disp)
    return urllib.parse.unquote(m.group(1)) if m else None


def file_info(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return {"name": path.name, "bytes": path.stat().st_size, "sha256": h.hexdigest()}


def safe_name(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "download"


# ---------------------------------------------------------------- handlers

def is_arcgis(url):
    return "/FeatureServer/" in url or "/MapServer/" in url


def download_arcgis(url, folder, where="1=1"):
    """Page through an ArcGIS layer/table; writes one feature per line (NDJSON)."""
    base = url.split("?")[0].rstrip("/")
    info = get_json(f"{base}?f=json")
    page = min(int(info.get("maxRecordCount") or 1000), 2000)
    oid = info.get("objectIdField") or next(
        (f["name"] for f in info.get("fields", []) if f.get("type") == "esriFieldTypeOID"), "OBJECTID")
    has_geom = info.get("type") == "Feature Layer"
    paged = info.get("advancedQueryCapabilities", {}).get("supportsPagination", False)
    params = {"where": where, "outFields": "*", "returnGeometry": str(has_geom).lower(),
              "outSR": "4326", "orderByFields": oid}

    # Prefer GeoJSON; fall back to Esri JSON when the server doesn't support it.
    fmt = "geojson"
    try:
        get_json(f"{base}/query", {**params, "resultRecordCount": 1, "f": "geojson"})
    except Exception:
        fmt = "json"

    def rows(resp):
        return resp.get("features", [])

    out = folder / "records.ndjson"
    count = 0
    with open(out, "w") as f:
        if paged:
            offset = 0
            while True:
                resp = get_json(f"{base}/query", {**params, "resultOffset": offset,
                                                  "resultRecordCount": page, "f": fmt})
                feats = rows(resp)
                for feat in feats:
                    f.write(json.dumps(feat) + "\n")
                count += len(feats)
                if not feats:
                    break
                offset += len(feats)
        else:
            ids = get_json(f"{base}/query", {"where": where, "returnIdsOnly": "true", "f": "json"})
            ids = sorted(ids.get("objectIds") or [])
            for i in range(0, len(ids), page):
                chunk = ",".join(map(str, ids[i:i + page]))
                resp = get_json(f"{base}/query", {**params, "objectIds": chunk, "f": fmt})
                for feat in rows(resp):
                    f.write(json.dumps(feat) + "\n")
                    count += 1
    return [out], count, f"{'geojson' if fmt == 'geojson' else 'esri-json'}-features-ndjson"


def download_odata(url, folder, name="records"):
    """Page through an Arlington datahub-v2 endpoint with $top/$skip."""
    out = folder / f"{safe_name(name)}.ndjson"
    count, skip = 0, 0
    sep = "&" if "?" in url else "?"
    with open(out, "w") as f:
        while True:
            data = get_json(f"{url}{sep}$top={ODATA_PAGE}&$skip={skip}")
            rows = data.get("value", data) if isinstance(data, dict) else data
            for row in rows:
                f.write(json.dumps(row) + "\n")
            count += len(rows)
            if len(rows) < ODATA_PAGE:
                break
            skip += ODATA_PAGE
    return out, count


def download_file(url, folder, name=None):
    tmp = folder / ".partial"
    suggested = save_stream(url, tmp)
    final = folder / safe_name(name or suggested or Path(urllib.parse.urlparse(url).path).name)
    tmp.replace(final)
    return final


def download_source(s, folder):
    """Returns (files, record_count or None, record_format)."""
    if s.get("session_url"):
        request(s["session_url"]).read()  # sets cookies some document stores require

    if s.get("list_url"):
        with request(s["list_url"]) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        hrefs = sorted(set(re.findall(r'href="([^"]+)"', html, flags=re.I)))
        pattern = re.compile(s.get("list_pattern") or ".", re.I)
        files = [download_file(urllib.parse.urljoin(s["list_url"], h), folder)
                 for h in hrefs if pattern.search(h)]
        if not files:
            raise RuntimeError("directory listing matched no files")
        return files, None, "original-files"

    if s.get("download_urls"):
        files = [download_file(item["url"], folder, item.get("name")) for item in s["download_urls"]]
        return files, None, "original-files"

    url = s["endpoint_url"]
    if is_arcgis(url):
        return download_arcgis(url, folder, s.get("query_where") or "1=1")
    if "datahub-v2.arlingtonva.us/api/" in url:
        out, n = download_odata(url, folder)
        files, total = [out], n
        for extra in s.get("extra_endpoints") or []:
            out, n = download_odata(extra, folder, extra.rstrip("/").split("/")[-1])
            files.append(out)
            total += n
        return files, total, "json-records-ndjson"
    return [download_file(url, folder)], None, "original-files"


# ---------------------------------------------------------------- driver

def selectable(s):
    if s["access_type"] not in DOWNLOADABLE:
        return False, f"access_type={s['access_type']}"
    if s.get("collection") in NEVER_FETCH:
        return False, f"collection={s['collection']}"
    if not (s.get("endpoint_url") or s.get("download_urls") or s.get("list_url")):
        return False, "no machine endpoint (manual or not yet known)"
    return True, ""


def write_manifest(out_dir, sources):
    rows = []
    for s in sources:
        meta_path = out_dir / s["jurisdiction"] / s["source_id"] / "_source.json"
        if not meta_path.exists():
            continue
        m = json.loads(meta_path.read_text())
        rows.append({
            "source_id": m["source_id"],
            "jurisdiction": m["jurisdiction"],
            "official_source": m["official_source"],
            "dataset_name": m["dataset_name"],
            "quoin_sections": ";".join(m["quoin_sections"]),
            "status": m["status"],
            "record_count": m.get("record_count") if m.get("record_count") is not None else "",
            "record_format": m.get("record_format", ""),
            "files": ";".join(f["name"] for f in m.get("files", [])),
            "retrieved_at": m["retrieved_at"],
            "error": m.get("error", ""),
        })
    path = out_dir / "manifest.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["source_id"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def main():
    global DELAY
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "data"))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--jurisdiction", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--list", action="store_true", help="print the plan and exit")
    ap.add_argument("--delay", type=float, default=DELAY, help="seconds between requests (be polite)")
    args = ap.parse_args()
    DELAY = args.delay

    sources = load_sources()
    errors = validate(sources)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    out_dir = Path(args.out).expanduser().resolve()
    plan, skipped = [], []
    for s in sources:
        if args.only and s["source_id"] not in args.only:
            continue
        if args.jurisdiction and s["jurisdiction"] not in args.jurisdiction:
            continue
        ok, why = selectable(s)
        (plan if ok else skipped).append((s, why))

    if args.list:
        for s, _ in plan:
            print(f"GET  {s['jurisdiction']:<15} {s['source_id']:<48} {s['official_source']}")
        for s, why in skipped:
            print(f"SKIP {s['jurisdiction']:<15} {s['source_id']:<48} ({why})")
        print(f"\n{len(plan)} to download, {len(skipped)} skipped")
        return 0

    failures = 0
    for s, _ in plan:
        folder = out_dir / s["jurisdiction"] / s["source_id"]
        meta_path = folder / "_source.json"
        if meta_path.exists() and not args.force and json.loads(meta_path.read_text()).get("status") == "ok":
            print(f"SKIP {s['source_id']} (already downloaded; --force to redo)")
            continue
        folder.mkdir(parents=True, exist_ok=True)
        meta = {
            "source_id": s["source_id"],
            "jurisdiction": s["jurisdiction"],
            "official_source": s.get("official_source") or "unknown",
            "dataset_name": s["dataset_name"],
            "quoin_sections": s["quoin_sections"],
            "parcel_key": s.get("parcel_key"),
            "retrieved_at": now(),
        }
        started = time.time()
        print(f"GET  {s['source_id']} ...", flush=True)
        try:
            files, count, fmt = download_source(s, folder)
            meta.update(status="ok", record_count=count, record_format=fmt,
                        files=[file_info(p) for p in files],
                        seconds=round(time.time() - started, 1))
            print(f"     ok: {len(files)} file(s), {count if count is not None else '?'} records")
        except Exception as e:
            failures += 1
            meta.update(status="failed", error=f"{type(e).__name__}: {e}")
            print(f"     FAILED: {meta['error']}")
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = write_manifest(out_dir, sources)
    print(f"\nmanifest: {manifest}")
    print(f"{len(plan) - failures}/{len(plan)} sources ok")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
