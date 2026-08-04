"""Download official California FHABS files and SFEI satellite waterbody metadata.

Run from the repository root.  File URLs are discovered from the official CKAN
metadata endpoint so this script remains valid when the rolling exports change.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
FHABS_PACKAGE = "https://data.ca.gov/api/3/action/package_show?id=ab672540-aecd-42f1-9b05-9aad326f97ec"
SATELLITE_WATERBODIES = "https://fhab-api.sfei.org/waterbody//csv"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "algae-drone-reproducible-analysis/1.0"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def datastore_rows(resource_id: str) -> list[dict]:
    """Fetch the complete CKAN datastore table without altering field values."""
    rows, offset = [], 0
    while True:
        api = f"https://data.ca.gov/api/3/action/datastore_search?resource_id={resource_id}&limit=1000&offset={offset}"
        payload = json.loads(fetch(api))
        page = payload["result"]["records"]
        rows.extend(page)
        if len(page) < 1000:
            return rows
        offset += len(page)


def save(path: Path, body: bytes) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {"file": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    downloaded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    package = json.loads(fetch(FHABS_PACKAGE))
    records = []
    resources = sorted(package["result"]["resources"], key=lambda r: r.get("format", "").upper() != "CSV")
    for resource in resources:
        name = resource["name"].lower()
        if not ("fhab" in name or "habs" in name):
            continue
        url = resource["url"]
        filename = url.rsplit("/", 1)[-1]
        if resource.get("format", "").upper() == "CSV":
            # The resource download endpoint is intermittently protected by a CDN.
            # CKAN's official API is the documented alternative and returns the same
            # published table.  Keep the direct URL as provenance and record API URL.
            rows = datastore_rows(resource["id"])
            columns = list(rows[0]) if rows else []
            dest = RAW / "fhabs" / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
                writer.writeheader(); writer.writerows(rows)
            body = dest.read_bytes()
            meta = {"file": str(dest.relative_to(ROOT)).replace("\\", "/"), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
            source_url = f"https://data.ca.gov/api/3/action/datastore_search?resource_id={resource['id']}"
        else:
            try:
                meta = save(RAW / "fhabs" / filename, fetch(url))
                source_url = url
            except Exception as exc:
                # Keep a machine-readable provenance record if the publisher's CDN
                # blocks non-browser retrieval of a supporting PDF.
                meta = {"file": "", "bytes": 0, "sha256": f"DOWNLOAD_FAILED: {type(exc).__name__}"}
                source_url = url
        records.append({"dataset": resource["name"], "source_url": source_url, "downloaded_at_utc": downloaded_at, **meta})
    satellite_meta = save(RAW / "satellite" / "sfei_waterbodies.csv", fetch(SATELLITE_WATERBODIES))
    records.append({"dataset": "SFEI FHAB satellite waterbody registry", "source_url": SATELLITE_WATERBODIES, "downloaded_at_utc": downloaded_at, **satellite_meta})
    with (RAW / "sources.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["dataset", "source_url", "downloaded_at_utc", "file", "bytes", "sha256"])
        writer.writeheader(); writer.writerows(records)
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    sys.exit(main())

