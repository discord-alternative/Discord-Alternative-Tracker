#!/usr/bin/env python3
"""Convert the comparison workbook into the data file the site reads.

    python scripts/build_data.py

Reads  data/discord_alternatives_categorized.xlsx
Writes pages/public/data.js

Needs openpyxl (pip install openpyxl).
"""

import datetime
import json
import pathlib
import re
import sys

import openpyxl

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "discord_alternatives_categorized.xlsx"
OUT = ROOT / "pages" / "public" / "data.js"

CONTROL = "Discord"
DIRECTORY_SHEET = "Sheet Directory"
GLOSSARY_SHEET = "Comparison Guide"

# One or more rows per platform, first column is the platform name.
RECORD_SHEETS = {"Pricing & Tiers", "Monetization Detail", "Research Sources"}
# Exactly one row per platform; shown transposed so it reads like the other sheets.
TRANSPOSE_SHEETS = {"Terms & Privacy"}
# Shown in full regardless of the selected platform.
TABLE_SHEETS = {"Discord Sources", "Subreddit Discovery"}
# Header sits on row 1 instead of row 2 for these.
NO_TITLE_ROW = {"Subreddit Discovery"}


def cell(value):
    if value is None:
        return ""
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_rows(ws):
    return [[cell(c) for c in row] for row in ws.iter_rows(values_only=True)]


def trim(row, width):
    row = row[:width]
    return row + [""] * (width - len(row))


def width_of(header):
    last = 0
    for i, h in enumerate(header):
        if h:
            last = i + 1
    return last


def read_directory(rows):
    groups = []
    for row in rows[2:]:
        cat, sheet, purpose = row[0], row[1], row[2]
        if cat and not sheet:
            name = re.sub(r"^\d+\s*-\s*", "", cat).strip()
            groups.append({"name": name, "sheets": []})
        elif sheet and groups:
            if sheet == DIRECTORY_SHEET:
                continue
            groups[-1]["sheets"].append({"name": sheet, "purpose": purpose})
    return groups


def read_matrix(name, rows, platforms):
    header = rows[1]
    found = [h for h in header[1:] if h]
    if found != platforms:
        sys.exit(f"{name}: platform columns differ from the At a Glance sheet")
    width = len(platforms) + 1
    out = []
    for row in rows[2:]:
        row = trim(row, width)
        label, values = row[0], row[1:]
        if not label and not any(values):
            continue
        if label and not any(values):
            out.append({"section": label})
        else:
            out.append({"label": label, "values": values})
    return {"kind": "matrix", "title": rows[0][0], "rows": out}


def read_records(name, rows, header_row=1):
    header = rows[header_row]
    width = width_of(header)
    columns = header[:width]
    body = [trim(r, width) for r in rows[header_row + 1:] if any(r[:width])]
    title = rows[0][0] if header_row == 1 else name
    return {"kind": "records", "title": title, "columns": columns, "rows": body}


def transpose(name, rows, platforms):
    header = rows[1]
    width = width_of(header)
    by_platform = {}
    for r in rows[2:]:
        r = trim(r, width)
        if r[0]:
            by_platform[r[0]] = r
    out = []
    for j in range(1, width):
        values = [by_platform.get(p, [""] * width)[j] for p in platforms]
        out.append({"label": header[j], "values": values})
    return {"kind": "matrix", "title": rows[0][0], "rows": out}


def read_glossary(rows):
    header = rows[1][:3]
    body = [r[:3] for r in rows[2:] if any(r[:3])]
    return {"kind": "glossary", "title": rows[0][0], "columns": header, "rows": body}


def main():
    wb = openpyxl.load_workbook(SRC, data_only=True)
    sheets = {ws.title: read_rows(ws) for ws in wb.worksheets}

    platforms = [h for h in sheets["At a Glance"][1][1:] if h]
    if platforms[0] != CONTROL:
        sys.exit(f"expected {CONTROL} in the first platform column")

    groups = read_directory(sheets[DIRECTORY_SHEET])

    as_of = ""
    for r in sheets[GLOSSARY_SHEET]:
        if r[0] == "As-of Date":
            as_of = r[1]

    data = {}
    for group in groups:
        for entry in group["sheets"]:
            name = entry["name"]
            rows = sheets[name]
            if name == GLOSSARY_SHEET:
                data[name] = read_glossary(rows)
            elif name in TRANSPOSE_SHEETS:
                data[name] = transpose(name, rows, platforms)
            elif name in RECORD_SHEETS:
                data[name] = read_records(name, rows)
            elif name in TABLE_SHEETS:
                data[name] = read_records(name, rows, header_row=0 if name in NO_TITLE_ROW else 1)
                data[name]["kind"] = "table"
            else:
                data[name] = read_matrix(name, rows, platforms)
            data[name]["purpose"] = entry["purpose"]

    payload = {
        "asOf": as_of,
        "control": CONTROL,
        "platforms": platforms,
        "groups": [{"name": g["name"], "sheets": [s["name"] for s in g["sheets"]]} for g in groups],
        "sheets": data,
    }
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text("window.TRACKER_DATA = " + text + ";\n", encoding="utf-8")

    matrix_rows = sum(len(s["rows"]) for s in data.values() if s["kind"] == "matrix")
    print(f"platforms: {len(platforms)}")
    print(f"sheets: {len(data)} in {len(groups)} groups")
    print(f"matrix rows: {matrix_rows}")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
