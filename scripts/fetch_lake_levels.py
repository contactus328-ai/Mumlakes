"""Fetch daily Mumbai lake water levels and record them to data/history.csv + data/latest.json.

Source: https://mumbailakewaterlevel.in/ (an aggregator whose page states its own
source as "BMC Hydraulic Engineer's Department, Bhandup Complex"). The page embeds a
static, JS-independent <section id="seo-content"> block with the day's figures, so a
plain HTTP fetch + HTML parse is enough (no browser automation needed).
"""

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://mumbailakewaterlevel.in/"
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
HISTORY_CSV = DATA_DIR / "history.csv"
LATEST_JSON = DATA_DIR / "latest.json"

LAKE_ORDER = [
    "Bhatsa",
    "Upper Vaitarna",
    "Middle Vaitarna",
    "Modak Sagar",
    "Tansa",
    "Vihar",
    "Tulsi",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def to_ml(indian_number: str) -> int:
    """Parse an Indian-comma-grouped number like '12,79,534' into an int."""
    return int(indian_number.replace(",", ""))


def fetch_seo_block() -> BeautifulSoup:
    resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    block = soup.find(id="seo-content")
    if block is None:
        raise RuntimeError(
            "Could not find #seo-content block — page structure may have changed."
        )
    return block


def parse(block: BeautifulSoup) -> dict:
    text = re.sub(r"\s+", " ", block.get_text(" ", strip=True))

    h1 = block.find("h1")
    if not h1:
        raise RuntimeError("No <h1> with report date found in #seo-content.")
    date_match = re.search(r",\s*(\d{1,2} \w+ \d{4})", h1.get_text())
    if not date_match:
        raise RuntimeError(f"Could not parse report date from heading: {h1.get_text()!r}")
    report_date = datetime.strptime(date_match.group(1), "%d %B %Y").date()

    total_match = re.search(
        r"Total storage.*?:\s*([\d.]+)%.*?\(([\d,]+)\s*ML of ([\d,]+)\s*ML total capacity\)",
        text,
    )
    if not total_match:
        raise RuntimeError("Could not parse total storage line from page text.")
    total_pct, total_ml, total_capacity_ml = total_match.groups()

    time_match = re.search(r"Report time:\s*([\d:]+)", text)
    report_time = time_match.group(1) if time_match else ""

    lakes = {}
    for li in block.find_all("li"):
        strong = li.find("strong")
        if not strong:
            continue
        name = strong.get_text(strip=True)
        li_match = re.search(r":\s*([\d.]+)%\s*full\s*\(([\d,]+)\s*ML\)", li.get_text())
        if not li_match:
            raise RuntimeError(f"Could not parse lake line for {name!r}: {li.get_text()!r}")
        pct, ml = li_match.groups()
        lakes[name] = {"pct": float(pct), "ml": to_ml(ml)}

    missing = [name for name in LAKE_ORDER if name not in lakes]
    if missing:
        raise RuntimeError(f"Missing expected lakes in scraped data: {missing}")

    return {
        "date": report_date.isoformat(),
        "report_time": report_time,
        "total_pct": float(total_pct),
        "total_ml": to_ml(total_ml),
        "total_capacity_ml": to_ml(total_capacity_ml),
        "lakes": lakes,
        "source_url": SOURCE_URL,
        "original_source": "BMC Hydraulic Engineer's Department, Bhandup Complex",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def csv_fieldnames() -> list[str]:
    fields = ["date", "report_time", "total_pct", "total_ml", "total_capacity_ml"]
    for name in LAKE_ORDER:
        slug = name.lower().replace(" ", "_")
        fields.append(f"{slug}_pct")
        fields.append(f"{slug}_ml")
    fields.append("fetched_at")
    return fields


def to_csv_row(record: dict) -> dict:
    row = {
        "date": record["date"],
        "report_time": record["report_time"],
        "total_pct": record["total_pct"],
        "total_ml": record["total_ml"],
        "total_capacity_ml": record["total_capacity_ml"],
        "fetched_at": record["fetched_at"],
    }
    for name in LAKE_ORDER:
        slug = name.lower().replace(" ", "_")
        row[f"{slug}_pct"] = record["lakes"][name]["pct"]
        row[f"{slug}_ml"] = record["lakes"][name]["ml"]
    return row


def upsert_history(record: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = csv_fieldnames()
    rows = []
    if HISTORY_CSV.exists():
        with HISTORY_CSV.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

    new_row = to_csv_row(record)
    replaced = False
    for i, row in enumerate(rows):
        if row["date"] == new_row["date"]:
            rows[i] = new_row
            replaced = True
            break
    if not replaced:
        rows.append(new_row)

    rows.sort(key=lambda r: r["date"])

    with HISTORY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_latest(record: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with LATEST_JSON.open("w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main() -> int:
    try:
        block = fetch_seo_block()
        record = parse(block)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    upsert_history(record)
    write_latest(record)
    print(f"Recorded {record['date']}: {record['total_pct']}% total storage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
