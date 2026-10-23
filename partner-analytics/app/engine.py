"""Safe analytics engine: the LLM fills in a typed query form, Python does all the arithmetic.

The model never writes SQL or code, and never calculates a number. It only picks values from fixed lists
(metric, grouping, period, filters). Every answer carries the form it was computed from, so it can be checked.
"""
import sqlite3
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from pydantic import BaseModel, Field

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "partners.db"

Metric = Literal[
    "revenue", "costs", "profit", "customers", "new_customers", "enquiries", "hours", "staff",
    "cash", "conversion_rate", "revenue_vs_plan", "locations",
    "months_to_second_location", "share_with_second_location",
]
GroupBy = Literal["none", "location", "state", "founder_type", "opening_year", "month"]
Period = Literal["last_month", "last_3_months", "last_6_months", "last_12_months", "all"]
FounderType = Literal["solo", "friends", "couple"]

# Flows add up over months; stocks are a level (averaged over months, then added across locations).
FLOWS = {"revenue": "revenue_eur", "costs": "costs_eur", "new_customers": "new_customers",
         "enquiries": "enquiries", "hours": "hours"}
STOCKS = {"customers": "customers", "staff": "staff", "cash": "cash_eur"}
PARTNER_LEVEL = {"months_to_second_location", "share_with_second_location", "locations"}
UNITS = {"revenue": "€", "costs": "€", "profit": "€", "cash": "€", "conversion_rate": "%",
         "revenue_vs_plan": "%", "share_with_second_location": "%", "months_to_second_location": "months"}


class QuerySpec(BaseModel):
    metric: Metric
    group_by: GroupBy = "none"
    period: Period = "last_month"
    growth: bool = Field(False, description="compare with the previous period of the same length")
    state: Optional[str] = None
    founder_type: Optional[FounderType] = None
    location: Optional[str] = None
    sort: Literal["desc", "asc"] = "desc"
    limit: int = Field(10, ge=1, le=60)


def load():
    with sqlite3.connect(DB_PATH) as con:
        partners = pd.read_sql("SELECT * FROM partners", con)
        monthly = pd.read_sql("SELECT * FROM monthly", con)
    partners["opening_year"] = partners["opened"].str[:4]
    return partners, monthly.merge(partners, on="location")


def _months(monthly, period, shift=0):
    months = sorted(monthly["month"].unique())
    n = {"last_month": 1, "last_3_months": 3, "last_6_months": 6, "last_12_months": 12}.get(period)
    if n is None:
        return months
    end = len(months) - shift * n
    return months[max(0, end - n):end]


def _filter(df, spec):
    if spec.state:
        df = df[df["state"].str.lower() == spec.state.lower()]
    if spec.founder_type:
        df = df[df["founder_type"] == spec.founder_type]
    if spec.location:
        df = df[df["location"].str.lower() == spec.location.lower()]
    return df


def _per_location(df, metric):
    """One value per location over the selected months (sums for flows, averages for stocks)."""
    g = df.groupby("location")
    if metric in FLOWS:
        out = g[FLOWS[metric]].sum()
    elif metric in STOCKS:
        out = g[STOCKS[metric]].mean()
    elif metric == "profit":
        out = g["revenue_eur"].sum() - g["costs_eur"].sum()
    elif metric == "conversion_rate":
        return g[["new_customers", "enquiries"]].sum()
    elif metric == "revenue_vs_plan":
        return g[["revenue_eur", "plan_revenue_eur"]].sum()
    return out.rename("value")


def _combine(per_loc, metric, keys):
    """Add up per-location values within each group; ratios are recomputed from their sums."""
    if metric == "conversion_rate":
        s = per_loc.groupby(keys)[["new_customers", "enquiries"]].sum()
        return (100 * s["new_customers"] / s["enquiries"]).rename("value")
    if metric == "revenue_vs_plan":
        s = per_loc.groupby(keys)[["revenue_eur", "plan_revenue_eur"]].sum()
        return (100 * (s["revenue_eur"] / s["plan_revenue_eur"] - 1)).rename("value")
    return per_loc.groupby(keys)["value"].sum()


def _monthly_value(df, spec, months):
    df = df[df["month"].isin(months)]
    if df.empty:
        return pd.Series(dtype=float)
    keys = {"none": None, "month": "month"}.get(spec.group_by, spec.group_by)
    if spec.group_by == "month":
        # Time series: total per month across locations.
        rows = []
        for month, part in df.groupby("month"):
            per_loc = _per_location(part, spec.metric)
            per_loc = per_loc.to_frame() if isinstance(per_loc, pd.Series) else per_loc
            per_loc["all"] = "all"
            rows.append((month, _combine(per_loc, spec.metric, "all").iloc[0]))
        return pd.Series(dict(rows), name="value")
    per_loc = _per_location(df, spec.metric)
    per_loc = per_loc.to_frame() if isinstance(per_loc, pd.Series) else per_loc
    info = df.drop_duplicates("location").set_index("location")
    if keys is None:
        per_loc["all"] = "all"
        keys = "all"
    elif keys != "location":
        per_loc[keys] = info.loc[per_loc.index, keys]
    else:
        per_loc = per_loc.copy()
        per_loc["location_key"] = per_loc.index
        keys = "location_key"
    return _combine(per_loc, spec.metric, keys)


def _partner_value(partners, spec):
    df = partners.copy()
    key = {"none": None, "month": None}.get(spec.group_by, spec.group_by)
    if spec.metric == "locations":
        return df.groupby(key)["location"].count() if key else pd.Series({"all": len(df)})

    def months_to_second(row):
        if not row["second_location_opened"]:
            return None
        a = [int(x) for x in row["opened"].split("-")]
        b = [int(x) for x in row["second_location_opened"].split("-")]
        return (b[0] - a[0]) * 12 + b[1] - a[1]

    df["m2"] = df.apply(months_to_second, axis=1)
    df["has2"] = df["m2"].notna() * 100.0
    col = "m2" if spec.metric == "months_to_second_location" else "has2"
    return df.groupby(key)[col].mean() if key else pd.Series({"all": df[col].mean()})


def run_query(spec: QuerySpec):
    """Return (table, notes). table has columns group, value (and previous, change_pct with growth)."""
    partners, monthly = load()
    notes = []
    if spec.metric in PARTNER_LEVEL:
        if spec.growth or spec.group_by == "month":
            notes.append("This figure is per location, not per month, so the period and growth were ignored.")
        partners = _filter(partners, spec)
        current = _partner_value(partners, spec)
        previous = None
    else:
        monthly = _filter(monthly, spec)
        months = _months(monthly, spec.period)
        notes.append(f"Months used: {months[0]} to {months[-1]}." if months else "No data for this period.")
        current = _monthly_value(monthly, spec, months)
        previous = None
        if spec.growth and spec.period != "all" and spec.group_by != "month":
            prev_months = _months(monthly, spec.period, shift=1)
            previous = _monthly_value(monthly, spec, prev_months)
            notes.append(f"Compared with {prev_months[0]} to {prev_months[-1]}.")

    table = current.rename("value").to_frame()
    table.index.name = "group"
    if previous is not None:
        table["previous"] = previous
        table["difference"] = table["value"] - table["previous"]
        # A percentage is misleading when the earlier value was zero or negative (e.g. a loss).
        prev = table["previous"].where(table["previous"] > 0)
        table["change_pct"] = 100 * (table["value"] / prev - 1)
        if (table["previous"] <= 0).any():
            notes.append("Change in % left out where the earlier value was zero or negative; see the difference.")
        sort_col = "change_pct" if table["change_pct"].notna().any() else "difference"
    else:
        sort_col = "value"
    table = table.reset_index().dropna(subset=["value"])
    if spec.group_by == "month":
        table = table.sort_values("group")
    else:
        table = table.sort_values(sort_col, ascending=spec.sort == "asc", na_position="last").head(spec.limit)
    return table.round(1), notes


def describe(spec: QuerySpec):
    """Plain-language version of the query form, shown under every answer."""
    parts = [spec.metric.replace("_", " ")]
    if spec.group_by != "none":
        parts.append(f"by {spec.group_by.replace('_', ' ')}")
    if spec.metric not in PARTNER_LEVEL:
        parts.append(spec.period.replace("_", " "))
    if spec.growth:
        parts.append("change vs. previous period")
    for name in ("state", "founder_type", "location"):
        if getattr(spec, name):
            parts.append(f"{name.replace('_', ' ')} = {getattr(spec, name)}")
    return ", ".join(parts)
