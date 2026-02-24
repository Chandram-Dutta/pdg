"""Extract tables from PP-600-PQ-001 PDF into CSV files for testing."""

import csv
from pathlib import Path

import pdfplumber

PDF_PATH = Path("PP-600-PQ-001, R0.pdf")
OUT_DIR = Path("csv")

LOADING_LEVELS = [
    "10%", "20%", "30%", "40%", "50%",
    "60%", "70%", "80%", "90%", "100%",
]


def clean(val):
    if val is None:
        return ""
    return val.replace("\n", " ").strip()


def write_csv(path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print(f"  Wrote {path} ({len(rows)} rows)")


def is_numeric(val):
    try:
        float(val)
        return True
    except (ValueError, TypeError):
        return False


def extract_data_rows(table, col_indices, extra_markers=()):
    """Extract data rows from a table using specified column indices.
    
    extra_markers: cell[0] values that are valid but non-numeric (e.g. 'TDD', 'THD')
    """
    rows = []
    for row in table:
        cells = [clean(c) for c in row]
        first = cells[0]
        if not first:
            continue
        if not is_numeric(first) and first.upper() not in extra_markers:
            continue
        extracted = []
        for ci in col_indices:
            if ci < len(cells):
                extracted.append(cells[ci])
            else:
                extracted.append("")
        rows.append(extracted)
    return rows


# ---------- Section 5.6 ----------

SEC_56_PAGES = {
    "10%": (13, 14), "20%": (14, 15), "30%": (16, 17), "40%": (17, 18),
    "50%": (18, 19), "60%": (19, 20), "70%": (20, 21), "80%": (21, 22),
    "90%": (22, 23), "100%": (23, 24),
}


def get_tables(pdf, page_indices, min_rows=3):
    """Get tables from pages, skipping tiny header/footer tables."""
    for pi in page_indices:
        for table in pdf.pages[pi].extract_tables():
            if len(table) >= min_rows:
                yield table


def extract_56_rows(table):
    """Extract rows from 9-col harmonic spectrum tables.
    
    Column layout varies between tables:
    - Some: [0]=order, [1]=Ia, [4]=Ib, [7]=Ic
    - Some: [0]=order, [1]=Ia, [3]=Ib, [6]=Ic
    Detect by checking which columns have data in the first data row.
    """
    rows = []
    # Find column indices from first data row
    ia_idx, ib_idx, ic_idx = 1, 4, 7  # default
    for row in table:
        cells = [clean(c) for c in row]
        if is_numeric(cells[0]):
            # Check which columns after [1] have data
            non_empty = [j for j in range(2, len(cells)) if cells[j]]
            if non_empty:
                ib_idx = non_empty[0]
                ic_idx = non_empty[1] if len(non_empty) > 1 else ib_idx + 3
            break

    for row in table:
        cells = [clean(c) for c in row]
        if not is_numeric(cells[0]):
            continue
        ia = cells[ia_idx] if ia_idx < len(cells) else ""
        ib = cells[ib_idx] if ib_idx < len(cells) else ""
        ic = cells[ic_idx] if ic_idx < len(cells) else ""
        rows.append([cells[0], ia, ib, ic])
    return rows


def parse_section_56(pdf):
    """Section 5.6: 9-col tables with varying column layouts."""
    out = OUT_DIR / "5.6"
    headers = ["Harmonic_Order", "Ia_pu", "Ib_pu", "Ic_pu"]

    for i, level in enumerate(LOADING_LEVELS):
        pages = SEC_56_PAGES[level]
        page_indices = list(range(pages[0], pages[1] + 1))
        rows = []
        for table in get_tables(pdf, page_indices):
            rows.extend(extract_56_rows(table))
        fname = f"{i+1:02d}_{level.replace('%','pct')}.csv"
        write_csv(out / fname, headers, rows)


# ---------- Section 7: sequential scan ----------

def classify_table(table):
    """Classify a section-7 table by column count and header text."""
    ncols = len(table[0])
    if ncols >= 20:
        return "verification"
    header_text = " ".join((c or "") for c in table[0]).lower()
    if "current" in header_text:
        return "current"
    if "voltage" in header_text:
        return "voltage"
    # Fallback: check second header row
    if len(table) > 1:
        header2 = " ".join((c or "") for c in table[1]).lower()
        if "current" in header2:
            return "current"
        if "voltage" in header2:
            return "voltage"
    return "unknown"


def extract_current_voltage_rows(table):
    """15-16 col layout: [0]=order, [1]=R, [4]=Y, [7]=B, [10]=IEEE_limit, [13]=pass_fail.
    Some tables have 15 cols where Y is at [4] and B at [6] or [7].
    """
    rows = []
    for row in table:
        cells = [clean(c) for c in row]
        first = cells[0]
        if not first:
            continue
        is_marker = first.upper() in ("TDD", "THD")
        if not is_marker and not is_numeric(first):
            continue
        ncols = len(cells)
        r_val = cells[1] if ncols > 1 else ""
        if ncols >= 16:
            y_val = cells[4]
            b_val = cells[7]
            limit_val = cells[10]
            pass_fail = cells[13]
        elif ncols >= 15:
            y_val = cells[4] if cells[4] else cells[3]
            b_val = cells[6] if cells[6] else (cells[7] if ncols > 7 and cells[7] else "")
            limit_val = cells[9] if cells[9] else ""
            pass_fail = cells[12] if cells[12] else ""
        else:
            y_val = cells[2] if ncols > 2 else ""
            b_val = cells[3] if ncols > 3 else ""
            limit_val = cells[4] if ncols > 4 else ""
            pass_fail = cells[5] if ncols > 5 else ""
        # Fill empty values by searching nearby
        if not y_val:
            for ci in range(3, min(6, ncols)):
                if cells[ci]:
                    y_val = cells[ci]
                    break
        if not b_val:
            for ci in range(6, min(10, ncols)):
                if cells[ci]:
                    b_val = cells[ci]
                    break
        if not limit_val:
            for ci in range(10, min(13, ncols)):
                if cells[ci]:
                    limit_val = cells[ci]
                    break
        if not pass_fail:
            for ci in range(13, min(16, ncols)):
                if cells[ci]:
                    pass_fail = cells[ci]
                    break
        rows.append([first, r_val, y_val, b_val, limit_val, pass_fail])
    return rows


def extract_verification_rows(table):
    """21-22 col layout for verification tables."""
    rows = []
    for row in table:
        cells = [clean(c) for c in row]
        if not is_numeric(cells[0]):
            continue
        ncols = len(cells)
        if ncols >= 22:
            rows.append([
                cells[0],
                cells[1], cells[4], cells[7],
                cells[10], cells[13], cells[16],
            ])
        elif ncols >= 21:
            rows.append([
                cells[0],
                cells[1], cells[4], cells[6],
                cells[9], cells[12], cells[15],
            ])
    return rows


def parse_section_7(pdf):
    """Scan pages 27–85 and classify tables by type, accumulating per loading level."""
    # Collect all classified table fragments in order
    current_fragments = []
    voltage_fragments = []
    verification_fragments = []

    for pi in range(27, 86):
        for table in get_tables(pdf, [pi]):
            ttype = classify_table(table)
            if ttype == "current":
                current_fragments.append(extract_current_voltage_rows(table))
            elif ttype == "voltage":
                voltage_fragments.append(extract_current_voltage_rows(table))
            elif ttype == "verification":
                verification_fragments.append(extract_verification_rows(table))

    # Group fragments into loading levels. Each loading level is a set of
    # consecutive fragments that together cover harmonics 2..50 (+ TDD/THD).
    def group_into_levels(fragments):
        """Group table fragments into 10 loading levels."""
        levels = []
        current_rows = []
        for frag in fragments:
            if not frag:
                continue
            first_order = frag[0][0]
            # If this fragment starts at harmonic 2, it's a new level
            # (unless we have nothing yet)
            if first_order == "2" and current_rows:
                levels.append(current_rows)
                current_rows = []
            current_rows.extend(frag)
        if current_rows:
            levels.append(current_rows)
        return levels

    current_levels = group_into_levels(current_fragments)
    voltage_levels = group_into_levels(voltage_fragments)
    verification_levels = group_into_levels(verification_fragments)

    # Write current CSVs
    current_dir = OUT_DIR / "7_current"
    headers_cv = ["Harmonic_Order", "Phase_R", "Phase_Y", "Phase_B", "IEEE_Limit_pct", "Limit_Passed"]
    for i, rows in enumerate(current_levels):
        level = LOADING_LEVELS[i] if i < len(LOADING_LEVELS) else f"{(i+1)*10}%"
        fname = f"{i+1:02d}_{level.replace('%','pct')}.csv"
        write_csv(current_dir / fname, headers_cv, rows)

    # Write voltage CSVs
    voltage_dir = OUT_DIR / "7_voltage"
    for i, rows in enumerate(voltage_levels):
        level = LOADING_LEVELS[i] if i < len(LOADING_LEVELS) else f"{(i+1)*10}%"
        fname = f"{i+1:02d}_{level.replace('%','pct')}.csv"
        write_csv(voltage_dir / fname, headers_cv, rows)

    # Write verification CSVs
    verification_dir = OUT_DIR / "7_verification"
    headers_v = [
        "Harmonic_Order",
        "Inverter_R", "Inverter_Y", "Inverter_B",
        "Model_R", "Model_Y", "Model_B",
    ]
    for i, rows in enumerate(verification_levels):
        level = LOADING_LEVELS[i] if i < len(LOADING_LEVELS) else f"{(i+1)*10}%"
        fname = f"{i+1:02d}_{level.replace('%','pct')}.csv"
        write_csv(verification_dir / fname, headers_v, rows)


# ---------- Section 9 ----------

def parse_section_9(pdf):
    out = OUT_DIR / "9"
    headers = ["Test_No", "Regulation_Clause", "Power_Dispatch_pu", "Compliance_Status"]
    rows = []
    # Page 92 has multiple small tables with different column layouts
    for table in pdf.pages[91].extract_tables():
        for row in table:
            cells = [clean(c) for c in row]
            if not cells[0] or not is_numeric(cells[0]):
                continue
            ncols = len(cells)
            if ncols == 4:
                rows.append(cells[:4])
            elif ncols == 5:
                # 5-col: [0]=test, [1]=clause, [2]=power (merged), [3]=empty, [4]=status
                power = cells[2] if cells[2] else cells[3]
                status = cells[4] if cells[4] else cells[3]
                rows.append([cells[0], cells[1], power, status])
    write_csv(out / "dc_injection.csv", headers, rows)


# ---------- Section 10 ----------

def parse_section_10(pdf):
    out = OUT_DIR / "10"
    headers = ["Cases", "Flicker", "Requirement", "Flicker_at_POI", "Status"]
    rows = []
    for table in get_tables(pdf, [89]):
        for row in table:
            cells = [clean(c) for c in row]
            if not cells[0]:
                continue
            low = cells[0].lower()
            if "case" in low or "flicker" in low:
                continue
            if len(cells) >= 5:
                rows.append(cells[:5])
    write_csv(out / "flicker_analysis.csv", headers, rows)


# ---------- Annexure B ----------

def parse_annexure_b(pdf):
    out = OUT_DIR / "annexure_b"
    # Actual PDF has 12 cols: [0]=Sr, [1]=Voltage, [2]=Comp, [3]=Material,
    # [4]=From1, [5]=From2, [6]=To1, [7]=To2,
    # [8]=CAD_Length, [9]=Additional, [10]=Total, [11]=No_of_Runs
    # From = From1 + " " + From2, To = To1 + " " + To2
    headers = [
        "Sr_No", "Voltage_Grade", "Comp", "Material",
        "From", "To", "CAD_Length", "Additional_Length",
        "Total_Length", "No_of_Runs",
    ]
    rows = []
    for table in get_tables(pdf, [96, 97, 98, 99]):
        for row in table:
            cells = [clean(c) for c in row]
            if not cells[0] or not is_numeric(cells[0]):
                continue
            ncols = len(cells)
            if ncols >= 12:
                from_val = f"{cells[4]} {cells[5]}".strip()
                to_val = f"{cells[6]} {cells[7]}".strip()
                rows.append([
                    cells[0], cells[1], cells[2], cells[3],
                    from_val, to_val,
                    cells[8], cells[9], cells[10], cells[11],
                ])
            else:
                padded = (cells + [""] * 10)[:10]
                rows.append(padded)
    write_csv(out / "cable_schedule.csv", headers, rows)


# ---------- Main ----------

def main():
    print(f"Opening {PDF_PATH}...")
    with pdfplumber.open(PDF_PATH) as pdf:
        print(f"  {len(pdf.pages)} pages found.\n")

        print("Section 5.6: Harmonic Spectrum of Inverter")
        parse_section_56(pdf)

        print("\nSection 7: Current / Voltage / Verification")
        parse_section_7(pdf)

        print("\nSection 9: DC Injection")
        parse_section_9(pdf)

        print("\nSection 10: Flicker Analysis")
        parse_section_10(pdf)

        print("\nAnnexure B: Cable Schedule")
        parse_annexure_b(pdf)

    print("\nDone! CSVs written to:", OUT_DIR.resolve())


if __name__ == "__main__":
    main()
