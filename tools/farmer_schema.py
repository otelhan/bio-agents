"""
BC dataset schema/coverage tool.
Ported directly from AI Farmer.yml meta code node.
"""
import csv, ssl, urllib.request, io, json

MAX_COVERAGE_ROWS   = 40
DTYPE_SAMPLE_NONEMPTY = 50
OUTPUT_COL_HINTS    = ["output", "prediction", "pred", "target", "label", "result"]

_CACHE: dict = {}


def _out(text: str) -> dict:
    return {"result": text}


def _load(url: str):
    if url in _CACHE:
        return _CACHE[url]
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(url, context=ctx, timeout=20) as f:
        txt = f.read().decode("utf-8")
    rows = [dict(r) for r in csv.DictReader(io.StringIO(txt))]
    _CACHE[url] = rows
    return rows


def _norm_str(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() in ("null", "none", "nan", "na"):
        return None
    return s


def _year_from_date(d):
    try:
        return int(str(d)[:4])
    except Exception:
        return None


def _infer_year(row, table_name):
    y = _norm_str(row.get("year"))
    if y:
        try:
            return int(float(y))
        except Exception:
            pass
    if table_name == "runs":
        return _year_from_date(row.get("start_date") or row.get("date"))
    else:
        return _year_from_date(row.get("treatment_date") or row.get("date"))


def _filter_by_scope(rows, scope, table_name):
    if scope == "both":
        return rows
    want = int(scope)
    return [r for r in rows if _infer_year(r, table_name) == want]


def _md_table(rows, headers):
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join(["---"] * len(headers)) + " |"]
    for r in rows:
        lines.append("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
    return "\n".join(lines)


def _is_int(s):
    try:
        if "." in s or "e" in s.lower():
            return False
        int(s)
        return True
    except Exception:
        return False


def _is_float(s):
    try:
        float(s)
        return True
    except Exception:
        return False


def _infer_dtype(values):
    if not values:
        return "unknown"
    bool_set = {"true", "false", "0", "1", "yes", "no"}
    if all(str(v).strip().lower() in bool_set for v in values):
        return "bool"
    if all(_is_int(str(v).strip()) for v in values):
        return "int"
    if all(_is_float(str(v).strip()) for v in values):
        return "float"
    return "string"


def _schema(rows):
    if not rows:
        return [], {}
    header = list(rows[0].keys())
    samples = {c: [] for c in header}
    nonempty = {c: 0 for c in header}
    for r in rows:
        for c in header:
            if nonempty[c] >= DTYPE_SAMPLE_NONEMPTY:
                continue
            v = _norm_str(r.get(c))
            if v is None:
                continue
            samples[c].append(v)
            nonempty[c] += 1
        if all(nonempty[c] >= DTYPE_SAMPLE_NONEMPTY for c in header):
            break
    dtype_map = {c: _infer_dtype(samples[c]) for c in header}
    return header, dtype_map


def _coverage(rows, header):
    nrows = len(rows)
    miss = {c: sum(1 for r in rows if _norm_str(r.get(c)) is None) for c in header}
    return nrows, miss


def _find_field(header, field_name):
    if field_name in header:
        return field_name
    low = field_name.lower()
    for c in header:
        if str(c).lower() == low:
            return c
    return None


def main(
    runs_csv_url: str,
    treatments_csv_url: str,
    action: str,
    dataset_scope: str = "both",
    table: str = "both",
    field_name: str = None,
) -> dict:

    action         = (_norm_str(action) or "").strip()
    dataset_scope  = (_norm_str(dataset_scope) or "both").strip()
    table          = (_norm_str(table) or "both").strip()
    field_name     = _norm_str(field_name)

    if action not in {"list_fields", "describe_field", "list_outputs", "dataset_diff", "coverage_stats"}:
        return _out(f"Error: unknown action '{action}'.")
    if dataset_scope not in {"2024", "2025", "both"}:
        dataset_scope = "both"
    if table not in {"runs", "treatments", "both"}:
        table = "both"

    try:
        runs_all = _load(runs_csv_url)
        trt_all  = _load(treatments_csv_url)
    except Exception as e:
        return _out(f"Could not load CSV(s): {e}")

    tables = ["runs", "treatments"] if table == "both" else [table]
    parts  = []

    if action == "list_fields":
        for t in tables:
            rows_all = runs_all if t == "runs" else trt_all
            rows = _filter_by_scope(rows_all, dataset_scope, t)
            header, dtype_map = _schema(rows)
            md = _md_table([[c, dtype_map.get(c, "unknown")] for c in header], ["field", "dtype"])
            parts.append(f"Fields available — {t} (scope={dataset_scope}):\n\n{md}")
        return _out("\n\n".join(parts))

    if action == "describe_field":
        if not field_name:
            return _out("No field name provided.")
        availability = []
        for t in tables:
            rows_all = runs_all if t == "runs" else trt_all
            rows = _filter_by_scope(rows_all, dataset_scope, t)
            header, dtype_map = _schema(rows)
            col = _find_field(header, field_name)
            if col is None:
                availability.append(f"- {field_name} is not present in {t} (scope={dataset_scope}).")
                continue
            nrows, miss = _coverage(rows, header)
            m  = miss.get(col, 0)
            mp = (m / nrows * 100.0) if nrows else 0.0
            availability.append(
                f"- {col} in {t} (scope={dataset_scope}): dtype={dtype_map.get(col, 'unknown')}, "
                f"rows={nrows}, missing={m} ({mp:.2f}%)."
            )
        return _out(f"Field: {field_name}\n\nAvailability:\n" + "\n".join(availability))

    if action == "list_outputs":
        for t in tables:
            rows_all = runs_all if t == "runs" else trt_all
            rows = _filter_by_scope(rows_all, dataset_scope, t)
            header, dtype_map = _schema(rows)
            out_cols = [c for c in header if any(h in str(c).lower() for h in OUTPUT_COL_HINTS)]
            if not out_cols:
                parts.append(f"No output-like fields found in {t} (scope={dataset_scope}).")
                continue
            md = _md_table([[c, dtype_map.get(c, "unknown")] for c in out_cols], ["field", "dtype"])
            parts.append(f"Output-like fields — {t} (scope={dataset_scope}):\n\n{md}")
        return _out("\n\n".join(parts))

    if action == "dataset_diff":
        for t in tables:
            rows_all = runs_all if t == "runs" else trt_all
            r24 = _filter_by_scope(rows_all, "2024", t)
            r25 = _filter_by_scope(rows_all, "2025", t)
            h24, _ = _schema(r24)
            h25, _ = _schema(r25)
            c24, c25   = set(h24), set(h25)
            only_24    = sorted(list(c24 - c25))
            only_25    = sorted(list(c25 - c24))
            common     = sorted(list(c24 & c25))
            parts.append(f"Schema differences — {t}\n")
            parts.append("Fields only in 2024:\n\n" + _md_table([[c] for c in only_24] or [["(none)"]], ["field"]))
            parts.append("Fields only in 2025:\n\n" + _md_table([[c] for c in only_25] or [["(none)"]], ["field"]))
            parts.append("Fields in both:\n\n"      + _md_table([[c] for c in common]  or [["(none)"]], ["field"]))
        return _out("\n\n".join(parts))

    if action == "coverage_stats":
        for t in tables:
            rows_all = runs_all if t == "runs" else trt_all
            rows = _filter_by_scope(rows_all, dataset_scope, t)
            header, dtype_map = _schema(rows)
            nrows, miss = _coverage(rows, header)
            rows_out = []
            for c in header:
                m   = int(miss.get(c, 0))
                pct = (m / nrows * 100.0) if nrows else 0.0
                rows_out.append([c, dtype_map.get(c, "unknown"), m, f"{pct:.2f}%"])
            rows_out.sort(key=lambda r: float(str(r[3]).replace("%", "")), reverse=True)
            rows_out = rows_out[:MAX_COVERAGE_ROWS]
            md = _md_table(rows_out, ["field", "dtype", "missing_count", "missing_pct"])
            parts.append(f"Coverage stats — {t} (scope={dataset_scope}): rows={nrows}, columns={len(header)}\n\n{md}")
        return _out("\n\n".join(parts))

    return _out("Error: unhandled action.")
