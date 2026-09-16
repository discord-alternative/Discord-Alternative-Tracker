#!/usr/bin/env python3
"""Convert the Discord-alternatives comparison workbook into site data.

Run:
    python scripts/build_data.py

Reads:
    data/discord_alternatives_categorized.xlsx

Writes:
    pages/public/data.js

Requires:
    pip install openpyxl
"""

import datetime
import json
import pathlib
import re
import sys

import openpyxl


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parent.parent

SRC = ROOT / "data" / "discord_alternatives_categorized.xlsx"
OUT = ROOT / "pages" / "public" / "data.js"


# ---------------------------------------------------------------------------
# Workbook structure
# ---------------------------------------------------------------------------

CONTROL = "Discord"

DIRECTORY_SHEET = "Sheet Directory"
GLOSSARY_SHEET = "Comparison Guide"
MASTER_SHEET = "Master"


# Sheets that exist for workbook organization / internal data and should NOT
# become pages on the website.
INTERNAL_SHEETS = {
    MASTER_SHEET,
}


# One or more rows per platform.
# The first column contains the platform name.
RECORD_SHEETS = {
    "Pricing & Tiers",
    "Monetization Detail",
    "Research Sources",
    "Website Links",
    "Verification Coverage",
}


# Exactly one row per platform.
# These are transposed into the same visual format as the matrix sheets.
TRANSPOSE_SHEETS = {
    "Terms & Privacy",
}


# Displayed as full tables rather than platform-comparison matrices.
TABLE_SHEETS = {
    "Discord Sources",
    "Subreddit Discovery",
}


# These sheets have their header in row 1 instead of row 2.
NO_TITLE_ROW = {
    "Subreddit Discovery",
}


# ---------------------------------------------------------------------------
# Cell conversion
# ---------------------------------------------------------------------------

def cell(value, number_format="General"):
    """Convert an Excel cell value into a site-safe string."""

    if value is None:
        return ""

    if isinstance(value, datetime.datetime):
        return value.date().isoformat()

    if isinstance(value, datetime.date):
        return value.isoformat()

    # Preserve percentage formatting from Excel.
    if (
        isinstance(value, (int, float))
        and isinstance(number_format, str)
        and number_format.endswith("%")
    ):
        if "." in number_format:
            decimals = len(
                number_format.split(".", 1)[1].rstrip("%")
            )
        else:
            decimals = 0

        return f"{value * 100:.{decimals}f}%"

    # Avoid output such as "20.0" when Excel really contains integer 20.
    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value).strip()


def read_rows(ws):
    """Read an entire worksheet into a list of string rows."""

    return [
        [
            cell(c.value, c.number_format)
            for c in row
        ]
        for row in ws.iter_rows()
    ]


def trim(row, width):
    """Force a row to exactly `width` columns."""

    row = row[:width]

    return row + [""] * (width - len(row))


def width_of(header):
    """Return the last populated header-column position."""

    last = 0

    for i, heading in enumerate(header):
        if heading:
            last = i + 1

    return last


# ---------------------------------------------------------------------------
# Sheet Directory
# ---------------------------------------------------------------------------

def read_directory(rows):
    """Read the Sheet Directory and build website navigation groups."""

    groups = []

    for row in rows[2:]:
        cat = row[0] if len(row) > 0 else ""
        sheet = row[1] if len(row) > 1 else ""
        purpose = row[2] if len(row) > 2 else ""

        # Category heading.
        if cat and not sheet:
            # Converts:
            #   "01 — Messaging & Features"
            # to:
            #   "Messaging & Features"
            name = re.sub(
                r"^\d+\s*[-—]\s*",
                "",
                cat,
            ).strip()

            groups.append({
                "name": name,
                "sheets": [],
            })

        # Actual sheet entry.
        elif sheet and groups:

            # The directory itself should not appear inside itself.
            if sheet == DIRECTORY_SHEET:
                continue

            # Master is internal canonical data.
            if sheet in INTERNAL_SHEETS:
                continue

            groups[-1]["sheets"].append({
                "name": sheet,
                "purpose": purpose,
            })

    # Master may be the only sheet inside the "Canonical Data" group.
    # Once Master is removed, don't send an empty group to the website.
    groups = [
        group
        for group in groups
        if group["sheets"]
    ]

    return groups


# ---------------------------------------------------------------------------
# Platform handling
# ---------------------------------------------------------------------------

def platform_columns(header, expected_platforms, start_column=1):
    """Find each platform's actual column position on a sheet.

    The website uses the At a Glance order, but individual workbook sheets
    are allowed to have their columns physically rearranged.

    Example normal matrix header:

        Metric | Discord | Stoat | Fenrid | ...

    start_column=1 means we begin looking in Excel column B.
    """

    found = {}

    for index in range(start_column, len(header)):
        name = header[index]

        if name in expected_platforms:
            found[name] = index

    missing = [
        platform
        for platform in expected_platforms
        if platform not in found
    ]

    return found, missing


def read_master_platforms(rows, expected_platforms):
    """Read only actual platform columns from Master.

    Current Master layout is approximately:

        Section
        Metric
        Discord
        Stoat
        Fenrid
        ...
        Source Row
        Notes

    Rather than assuming everything after column B is a platform, only names
    already known from At a Glance are accepted.

    This automatically ignores:
        Section
        Metric
        Source Row
        Notes
        future internal metadata columns
    """

    if len(rows) < 2:
        return []

    header = rows[1]

    return [
        heading
        for heading in header[2:]
        if heading in expected_platforms
    ]


def validate_master(sheets, platforms):
    """Ensure Master contains all website platforms.

    Master does NOT have to use the same physical column order as
    At a Glance.

    At a Glance controls site display order.
    Master controls canonical workbook data.
    """

    if MASTER_SHEET not in sheets:
        print(
            "warning: Master sheet not found",
            file=sys.stderr,
        )
        return

    master_platforms = read_master_platforms(
        sheets[MASTER_SHEET],
        platforms,
    )

    if not master_platforms:
        sys.exit(
            "Master: no recognized platform columns found"
        )

    missing = [
        platform
        for platform in platforms
        if platform not in master_platforms
    ]

    if missing:
        sys.exit(
            "Master is missing platform columns: "
            + ", ".join(missing)
        )

    print(
        f"Master: {len(master_platforms)} "
        "platform columns validated"
    )


# ---------------------------------------------------------------------------
# Matrix sheets
# ---------------------------------------------------------------------------

def read_matrix(name, rows, platforms):
    """Read a normal comparison matrix.

    Expected general layout:

        Row 1: Sheet title
        Row 2: Metric | Discord | Stoat | ...
        Row 3+: comparison data

    The physical workbook column order does not need to match the site's
    platform order. Columns are matched by platform name.
    """

    if len(rows) < 2:
        sys.exit(
            f"{name}: sheet does not contain a header row"
        )

    header = rows[1]

    column_map, missing = platform_columns(
        header,
        platforms,
        start_column=1,
    )

    if missing:
        sys.exit(
            f"{name}: missing platform columns: "
            + ", ".join(missing)
        )

    out = []

    for row in rows[2:]:
        label = row[0] if row else ""

        values = []

        # Always output values in the At a Glance platform order.
        for platform in platforms:
            column = column_map[platform]

            if column < len(row):
                values.append(row[column])
            else:
                values.append("")

        # Completely empty row.
        if not label and not any(values):
            continue

        # A label with no platform values is a section heading.
        if label and not any(values):
            out.append({
                "section": label,
            })

        # Normal metric row.
        else:
            out.append({
                "label": label,
                "values": values,
            })

    title = (
        rows[0][0]
        if rows and rows[0]
        else name
    )

    return {
        "kind": "matrix",
        "title": title,
        "rows": out,
    }


# ---------------------------------------------------------------------------
# Record-style sheets
# ---------------------------------------------------------------------------

def read_records(name, rows, header_row=1):
    """Read a normal row-oriented table."""

    if len(rows) <= header_row:
        return {
            "kind": "records",
            "title": name,
            "columns": [],
            "rows": [],
        }

    header = rows[header_row]

    width = width_of(header)

    columns = header[:width]

    body = []

    for row in rows[header_row + 1:]:
        row = trim(row, width)

        # Ignore category/group heading rows that contain no record data.
        if not any(row[1:width]):
            continue

        body.append(row)

    if header_row == 1:
        title = (
            rows[0][0]
            if rows and rows[0]
            else name
        )
    else:
        title = name

    return {
        "kind": "records",
        "title": title,
        "columns": columns,
        "rows": body,
    }


# ---------------------------------------------------------------------------
# Platform-row sheets
# ---------------------------------------------------------------------------

def transpose(name, rows, platforms):
    """Convert one-row-per-platform sheets into comparison matrices.

    Terms & Privacy currently uses this structure.
    """

    if len(rows) < 2:
        return {
            "kind": "matrix",
            "title": name,
            "rows": [],
        }

    header = rows[1]

    width = width_of(header)

    by_platform = {}

    for row in rows[2:]:
        row = trim(row, width)

        platform = row[0]

        if platform:
            by_platform[platform] = row

    out = []

    # Column 0 is the platform name.
    # Everything after it becomes a comparison metric.
    for column in range(1, width):
        label = header[column]

        if not label:
            continue

        values = []

        for platform in platforms:
            platform_row = by_platform.get(
                platform,
                [""] * width,
            )

            values.append(
                platform_row[column]
                if column < len(platform_row)
                else ""
            )

        out.append({
            "label": label,
            "values": values,
        })

    title = (
        rows[0][0]
        if rows and rows[0]
        else name
    )

    return {
        "kind": "matrix",
        "title": title,
        "rows": out,
    }


# ---------------------------------------------------------------------------
# Comparison Guide
# ---------------------------------------------------------------------------

def read_glossary(rows):
    """Read Comparison Guide."""

    if len(rows) < 2:
        return {
            "kind": "glossary",
            "title": GLOSSARY_SHEET,
            "columns": [],
            "rows": [],
        }

    header = rows[1][:3]

    body = [
        row[:3]
        for row in rows[2:]
        if any(row[:3])
    ]

    title = (
        rows[0][0]
        if rows and rows[0]
        else GLOSSARY_SHEET
    )

    return {
        "kind": "glossary",
        "title": title,
        "columns": header,
        "rows": body,
    }


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def main():
    if not SRC.exists():
        sys.exit(
            f"workbook not found: {SRC}"
        )

    # data_only=True means the site receives calculated values rather than
    # Excel formula strings.
    wb = openpyxl.load_workbook(
        SRC,
        data_only=True,
    )

    sheets = {
        ws.title: read_rows(ws)
        for ws in wb.worksheets
    }

    # -----------------------------------------------------------------------
    # Required sheets
    # -----------------------------------------------------------------------

    required = {
        DIRECTORY_SHEET,
        GLOSSARY_SHEET,
        "At a Glance",
    }

    missing_required = [
        name
        for name in required
        if name not in sheets
    ]

    if missing_required:
        sys.exit(
            "missing required workbook sheets: "
            + ", ".join(missing_required)
        )

    # -----------------------------------------------------------------------
    # Platform list
    # -----------------------------------------------------------------------

    # At a Glance is the authority for website platform order.
    #
    # Expected:
    #   A = metric
    #   B = Discord
    #   C = Stoat
    #   ...
    platforms = [
        heading
        for heading in sheets["At a Glance"][1][1:]
        if heading
    ]

    if not platforms:
        sys.exit(
            "At a Glance: no platform columns found"
        )

    if platforms[0] != CONTROL:
        sys.exit(
            f"expected {CONTROL} "
            "in the first platform column"
        )

    # Detect duplicate platform headings.
    duplicates = sorted({
        platform
        for platform in platforms
        if platforms.count(platform) > 1
    })

    if duplicates:
        sys.exit(
            "At a Glance contains duplicate platform columns: "
            + ", ".join(duplicates)
        )

    # -----------------------------------------------------------------------
    # Validate canonical Master
    # -----------------------------------------------------------------------

    validate_master(
        sheets,
        platforms,
    )

    # -----------------------------------------------------------------------
    # Navigation groups
    # -----------------------------------------------------------------------

    groups = read_directory(
        sheets[DIRECTORY_SHEET]
    )

    # -----------------------------------------------------------------------
    # Workbook as-of date
    # -----------------------------------------------------------------------

    as_of = ""

    for row in sheets[GLOSSARY_SHEET]:
        if row and row[0] == "As-of Date":
            as_of = (
                row[1]
                if len(row) > 1
                else ""
            )
            break

    # -----------------------------------------------------------------------
    # Convert site-visible sheets
    # -----------------------------------------------------------------------

    data = {}

    for group in groups:
        for entry in group["sheets"]:
            name = entry["name"]

            if name not in sheets:
                print(
                    "warning: Sheet Directory references "
                    f"missing sheet: {name}",
                    file=sys.stderr,
                )
                continue

            rows = sheets[name]

            if name == GLOSSARY_SHEET:
                result = read_glossary(rows)

            elif name in TRANSPOSE_SHEETS:
                result = transpose(
                    name,
                    rows,
                    platforms,
                )

            elif name in RECORD_SHEETS:
                result = read_records(
                    name,
                    rows,
                )

            elif name in TABLE_SHEETS:
                result = read_records(
                    name,
                    rows,
                    header_row=(
                        0
                        if name in NO_TITLE_ROW
                        else 1
                    ),
                )

                result["kind"] = "table"

            else:
                result = read_matrix(
                    name,
                    rows,
                    platforms,
                )

            result["purpose"] = entry["purpose"]

            data[name] = result

    # -----------------------------------------------------------------------
    # Remove directory entries for sheets that were missing
    # -----------------------------------------------------------------------

    clean_groups = []

    for group in groups:
        visible_sheets = [
            entry["name"]
            for entry in group["sheets"]
            if entry["name"] in data
        ]

        if visible_sheets:
            clean_groups.append({
                "name": group["name"],
                "sheets": visible_sheets,
            })

    # -----------------------------------------------------------------------
    # Build JavaScript payload
    # -----------------------------------------------------------------------

    payload = {
        "asOf": as_of,
        "control": CONTROL,
        "platforms": platforms,
        "groups": clean_groups,
        "sheets": data,
    }

    text = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    # Make sure the output folder exists.
    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUT.write_text(
        "window.TRACKER_DATA = "
        + text
        + ";\n",
        encoding="utf-8",
    )

    # -----------------------------------------------------------------------
    # Build report
    # -----------------------------------------------------------------------

    matrix_rows = sum(
        len(sheet["rows"])
        for sheet in data.values()
        if sheet["kind"] == "matrix"
    )

    record_rows = sum(
        len(sheet["rows"])
        for sheet in data.values()
        if sheet["kind"] in {
            "records",
            "table",
        }
    )

    print(
        f"platforms: {len(platforms)}"
    )

    print(
        "platform order: "
        + " -> ".join(platforms)
    )

    print(
        f"sheets: {len(data)} "
        f"in {len(clean_groups)} groups"
    )

    print(
        f"matrix rows: {matrix_rows}"
    )

    print(
        f"record/table rows: {record_rows}"
    )

    if MASTER_SHEET in sheets:
        print(
            "Master: validated as canonical workbook data "
            "(not exported as a site page)"
        )

    print(
        f"wrote {OUT.relative_to(ROOT)} "
        f"({OUT.stat().st_size:,} bytes)"
    )


if __name__ == "__main__":
    main()