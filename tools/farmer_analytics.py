"""
BC production data analytics engine.
Ported directly from AI Farmer.yml Dify code node.
"""
import csv, ssl, urllib.request, io, math, statistics

RUNS_NUM = {
    "fermentation_temp_c", "run_period_days", "initial_ph", "inoculum_pct",
    "carbon_concentration_gL", "yeast_extract_gL", "peptone_gL",
    "tray_count", "tray_area_m2", "liquid_depth_cm",
    "wet_mass_total_g", "dry_mass_total_g", "yield_per_m2_gm2",
    "avg_thickness_mm", "thickness_variation_pct",
    "defects_pct", "contamination_flag", "avg_process_deviation_pct", "year"
}

TRT_NUM = {
    "sample_area_m2", "sample_dry_mass_g", "sample_thickness_mm",
    "conditioning_rh_pct", "conditioning_temp_c", "final_moisture_pct",
    "plasticizer_pct",
    "tensile_strength_mpa", "elongation_pct", "youngs_modulus_mpa", "year"
}

ALLOWED_DATASETS   = {"runs", "treatments"}
ALLOWED_INTENTS    = {"summary", "filter_table", "best", "compare", "trend",
                      "feature_importance", "anomaly_detection"}
ALLOWED_AGG        = {"sum", "avg", "median", "min", "max", "count"}
ALLOWED_GROUP_BY   = {"none", "recipe", "year", "month", "recipe_year",
                      "drying_method", "pressing_level", "surface_class"}

RUNS_DEFAULT_METRIC = "yield_per_m2_gm2"
TRT_DEFAULT_METRIC  = "tensile_strength_mpa"


def _load(url: str):
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(url, context=ctx, timeout=15) as f:
        txt = f.read().decode("utf-8")
    return [dict(r) for r in csv.DictReader(io.StringIO(txt))]


def _norm_str(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() in ("null", "none", "nan", "na"):
        return None
    return s


def _f(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "" or s.lower() in ("nan", "na", "null", "none"):
        return None
    try:
        return float(s)
    except Exception:
        return None


def _i(x):
    v = _f(x)
    return None if v is None else int(v)


def _bool(x, default=False):
    if isinstance(x, bool):
        return x
    s = _norm_str(x)
    if s is None:
        return default
    if s.lower() in ("true", "1", "yes", "y"):
        return True
    if s.lower() in ("false", "0", "no", "n"):
        return False
    return default


def _int(x, default=0, min_v=None, max_v=None):
    s = _norm_str(x)
    if s is None:
        v = default
    else:
        try:
            v = int(float(s))
        except Exception:
            v = default
    if min_v is not None:
        v = max(min_v, v)
    if max_v is not None:
        v = min(max_v, v)
    return v


def _float_or_none(x):
    s = _norm_str(x)
    if s is None:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _year_from(d):
    try:
        return int(str(d).split("-")[0])
    except Exception:
        return None


def _month_from(d):
    try:
        return str(d)[:7]
    except Exception:
        return None


def _cast_runs(rows):
    for r in rows:
        r["year"]  = _year_from(r.get("start_date"))
        r["month"] = _month_from(r.get("start_date"))
        for c in RUNS_NUM:
            if c in ("tray_count", "run_period_days", "contamination_flag", "year"):
                r[c] = _i(r.get(c))
            else:
                r[c] = _f(r.get(c))
    return rows


def _cast_trt(rows):
    for r in rows:
        r["year"]  = _year_from(r.get("treatment_date"))
        r["month"] = _month_from(r.get("treatment_date"))
        for c in TRT_NUM:
            if c == "year":
                r[c] = _i(r.get(c))
            else:
                r[c] = _f(r.get(c))
    return rows


def _md(rows, cols, title, subtitle, limit=25):
    rows = rows[:limit]
    header = "| " + " | ".join(cols) + " |"
    sep    = "| " + " | ".join(["---"] * len(cols)) + " |"
    body   = ["| " + " | ".join("" if r.get(c) is None else str(r.get(c))
                                 for c in cols) + " |"
              for r in rows]
    return f"### {title}\n{subtitle}\n\n" + "\n".join([header, sep] + body)


def _agg(vals, how):
    xs = [v for v in vals if v is not None]
    if not xs:
        return None
    if how == "sum":    return sum(xs)
    if how == "avg":    return sum(xs) / len(xs)
    if how == "median": return statistics.median(xs)
    if how == "min":    return min(xs)
    if how == "max":    return max(xs)
    if how == "count":  return len(xs)
    return sum(xs) / len(xs)


def _pearson(x, y):
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < 5:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num  = sum((a - mx) * (b - my) for a, b in pairs)
    denx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    deny = math.sqrt(sum((b - my) ** 2 for b in ys))
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def _zflag(rows, metric, z=2.0):
    vals = [r.get(metric) for r in rows if r.get(metric) is not None]
    if len(vals) < 8:
        return []
    mu = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals))
    if sd == 0:
        return []
    out = []
    for r in rows:
        v = r.get(metric)
        if v is None:
            continue
        zz = (v - mu) / sd
        if abs(zz) >= z:
            rr = dict(r)
            rr["z_score"] = round(zz, 2)
            out.append(rr)
    out.sort(key=lambda r: abs(r["z_score"]), reverse=True)
    return out


def main(
    runs_csv_url: str,
    treatments_csv_url: str,
    dataset: str = "runs",
    intent: str = "summary",
    year: int = None,
    recipe: str = None,
    metric: str = None,
    aggregation: str = "avg",
    group_by: str = "none",
    top_k: int = 5,
    min_defects_pct: float = None,
    max_defects_pct: float = None,
    only_contaminated: bool = False,
    as_table: bool = False,
) -> dict:

    dataset     = (_norm_str(dataset) or "runs").lower()
    if dataset not in ALLOWED_DATASETS:
        dataset = "runs"

    intent      = (_norm_str(intent) or "summary").lower()
    if intent not in ALLOWED_INTENTS:
        intent = "summary"

    recipe      = _norm_str(recipe)
    recipe      = recipe.lower() if isinstance(recipe, str) else None

    metric      = _norm_str(metric)

    aggregation = (_norm_str(aggregation) or "avg").lower()
    if aggregation not in ALLOWED_AGG:
        aggregation = "avg"

    group_by    = (_norm_str(group_by) or "none").lower()
    if group_by not in ALLOWED_GROUP_BY:
        group_by = "none"

    min_defects_pct = _float_or_none(min_defects_pct)
    max_defects_pct = _float_or_none(max_defects_pct)
    if min_defects_pct == 0:
        min_defects_pct = None
    if max_defects_pct == 0:
        max_defects_pct = None

    only_contaminated = _bool(only_contaminated, default=False)
    as_table          = _bool(as_table, default=False)

    y    = _int(year, default=0)
    year = y if y != 0 else None
    top_k = _int(top_k, default=5, min_v=1, max_v=100)

    try:
        runs = _cast_runs(_load(runs_csv_url))
        trt  = _cast_trt(_load(treatments_csv_url))
    except Exception as e:
        return {"result": f"Could not load CSV(s): {e}"}

    rows = runs if dataset == "runs" else trt

    # --- Filtering ---
    q = rows
    if year is not None:
        q = [r for r in q if r.get("year") == year]
    if recipe:
        q = [r for r in q if str(r.get("recipe", "")).lower() == recipe]
    if dataset == "runs":
        if only_contaminated:
            q = [r for r in q if r.get("contamination_flag") == 1]
        if min_defects_pct is not None:
            q = [r for r in q if r.get("defects_pct") is not None and r["defects_pct"] >= float(min_defects_pct)]
        if max_defects_pct is not None:
            q = [r for r in q if r.get("defects_pct") is not None and r["defects_pct"] <= float(max_defects_pct)]

    if not q:
        return {"result": f"No rows found for dataset={dataset}, year={year or 'any'}, recipe={recipe or 'any'}."}

    if metric is None:
        metric = RUNS_DEFAULT_METRIC if dataset == "runs" else TRT_DEFAULT_METRIC

    # --- Table output ---
    if as_table or intent == "filter_table":
        cols = (["run_id", "start_date", "end_date", "year", "recipe",
                  "fermentation_temp_c", "initial_ph", "carbon_concentration_gL",
                  "tray_area_m2", "liquid_depth_cm",
                  "dry_mass_total_g", "yield_per_m2_gm2", "avg_thickness_mm",
                  "defects_pct", "contamination_flag", "avg_process_deviation_pct"]
                 if dataset == "runs"
                 else ["treatment_id", "run_id", "year", "drying_method", "pressing_level",
                       "final_moisture_pct", "plasticizer_type", "plasticizer_pct",
                       "tensile_strength_mpa", "elongation_pct", "youngs_modulus_mpa", "surface_class"])
        q2 = sorted(q, key=lambda r: (r.get("year") or 0,
                                       r.get("run_id") or r.get("treatment_id") or ""))
        return {"result": _md(q2, cols, "Filtered Results",
                              f"dataset={dataset}, year={year or 'any'}, recipe={recipe or 'any'}",
                              limit=50)}

    # --- Summary ---
    if intent == "summary":
        val = _agg([r.get(metric) for r in q], aggregation)
        return {"result": f"{dataset} | {aggregation}({metric}) for year={year or 'any'}, "
                          f"recipe={recipe or 'any'} = {None if val is None else round(val, 2)}"}

    # --- Compare / Trend ---
    if intent in ("compare", "trend"):
        if group_by == "none":
            return {"result": "Set group_by to recipe/year/month/recipe_year/"
                              "drying_method/pressing_level/surface_class for compare/trend."}
        buckets = {}
        for r in q:
            if group_by == "recipe_year":
                k = (r.get("recipe", "unknown"), r.get("year", "unknown"))
            elif group_by == "month":
                k = r.get("month")
            else:
                k = r.get(group_by)
            if k in (None, "", "null"):
                k = "unknown"
            buckets.setdefault(k, []).append(r)

        out = []
        if group_by == "recipe_year":
            for (rec, yr), items in buckets.items():
                out.append({"recipe": rec, "year": yr,
                             f"{aggregation}_{metric}": _agg([i.get(metric) for i in items], aggregation),
                             "n": len(items)})
            out.sort(key=lambda x: (str(x["recipe"]), int(x["year"]) if str(x["year"]).isdigit() else 0))
            cols = ["recipe", "year", f"{aggregation}_{metric}", "n"]
        else:
            for k, items in buckets.items():
                out.append({"group": k,
                             f"{aggregation}_{metric}": _agg([i.get(metric) for i in items], aggregation),
                             "n": len(items)})
            out.sort(key=lambda x: str(x["group"]))
            cols = ["group", f"{aggregation}_{metric}", "n"]

        return {"result": _md(out, cols, f"{metric} by {group_by}",
                              f"dataset={dataset}, year={year or 'any'}, recipe={recipe or 'any'}",
                              limit=100)}

    # --- Best ---
    if intent == "best":
        ranked = [r for r in q if r.get(metric) is not None]
        ranked.sort(key=lambda r: r.get(metric), reverse=True)
        cols = (["run_id", "start_date", "recipe", metric, "dry_mass_total_g",
                  "avg_thickness_mm", "defects_pct"]
                 if dataset == "runs"
                 else ["treatment_id", "run_id", "drying_method", "pressing_level",
                       metric, "surface_class"])
        return {"result": _md(ranked[:top_k], cols, f"Top {top_k} by {metric}",
                              f"dataset={dataset}, year={year or 'any'}, recipe={recipe or 'any'}",
                              limit=top_k)}

    # --- Feature importance ---
    if intent == "feature_importance":
        if dataset != "runs":
            return {"result": "feature_importance is implemented for dataset=runs."}
        candidates = ["fermentation_temp_c", "initial_ph", "inoculum_pct",
                      "carbon_concentration_gL", "yeast_extract_gL", "peptone_gL",
                      "tray_area_m2", "liquid_depth_cm", "run_period_days",
                      "avg_process_deviation_pct", "thickness_variation_pct"]
        y_vals = [r.get(metric) for r in q]
        scores = []
        for c in candidates:
            x_vals = [r.get(c) for r in q]
            rxy = _pearson(x_vals, y_vals)
            if rxy is not None:
                scores.append({"feature": c, "corr": round(rxy, 3)})
        scores.sort(key=lambda d: abs(d["corr"]), reverse=True)
        return {"result": _md(scores[:top_k], ["feature", "corr"],
                              f"Top drivers for {metric}",
                              f"(Pearson correlation; dataset=runs, year={year or 'any'}, recipe={recipe or 'any'})",
                              limit=top_k)}

    # --- Anomaly detection ---
    if intent == "anomaly_detection":
        if dataset != "runs":
            return {"result": "anomaly_detection is implemented for dataset=runs."}
        z_out = _zflag(q, metric, z=2.0)
        seen, out = set(), []

        def add(r, reasons):
            key = r.get("run_id") or (r.get("start_date"), r.get("recipe"))
            if key in seen:
                return
            rr = dict(r)
            rr["reasons"] = "; ".join(reasons)
            out.append(rr)
            seen.add(key)

        for r in z_out:
            add(r, [f"z={r.get('z_score')}"])
        for r in q:
            reasons = []
            if r.get("contamination_flag") == 1:
                reasons.append("contamination")
            if r.get("defects_pct") is not None and r["defects_pct"] >= 15:
                reasons.append("high_defects>=15")
            if r.get("avg_process_deviation_pct") is not None and r["avg_process_deviation_pct"] >= 2.0:
                reasons.append("high_deviation>=2.0")
            if reasons:
                add(r, reasons)

        out.sort(key=lambda r: (abs(r.get("z_score") or 0), r.get("defects_pct") or 0), reverse=True)
        cols = ["run_id", "start_date", "recipe", metric, "z_score",
                "defects_pct", "contamination_flag", "avg_process_deviation_pct", "reasons"]
        return {"result": _md(out[:top_k], cols, f"Anomalies for {metric}",
                              f"dataset=runs, year={year or 'any'}, recipe={recipe or 'any'}",
                              limit=top_k)}

    return {"result": f"Unknown intent: {intent}"}
