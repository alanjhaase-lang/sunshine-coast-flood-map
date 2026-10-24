#!/usr/bin/env python3
"""Rainfall totals for Twin Waters (rain.json): "since 9am" and the last 7 rain days.

BOM convention: a rain day runs 9am to 9am local time, and a daily total is
filed against the date on which its 24 hours END (e.g. the total for
2026-10-24 is 9am 23 Oct -> 9am 24 Oct).

Sources (all official Bureau of Meteorology, standard library only):
  * IDQ60920.xml (QLD 10-minute observations, also used for wind):
      rainfall      = rain since 9am (current, still-running rain day)
      rainfall_24hr = the most recent completed rain day (24 h to 9am)
  * Daily Weather Observations CSV (IDCJDW4081 Sunshine Coast Airport,
      IDCJDW4091 Nambour) for the earlier completed rain days of the
      current/previous month.
  * The previous rain.json: days already on file are kept, so a missing
      BOM product does not lose history (a small rolling history).

week_mm = rain since 9am (current day) + the 6 completed rain days before it,
i.e. 7 rain days from 9am six days ago up to the latest observation.

On failure of the 10-minute feed the previous file is kept and marked stale.
"""
import csv
import datetime as dt
import io
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from update_data import HOME, RADIUS_KM, UA, haversine_km

BNE = ZoneInfo("Australia/Brisbane")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "rain.json")
SRC = "https://www.bom.gov.au/fwo/IDQ60920.xml"
OBS_PAGE = "https://www.bom.gov.au/products/IDQ60801/IDQ60801.{wmo}.shtml"
DWO_CSV = "https://www.bom.gov.au/climate/dwo/{ym}/text/{dwo}.{ym}.csv"
DWO_PAGE = "https://www.bom.gov.au/climate/dwo/{dwo}.latest.shtml"
WEEK_DAYS = 7
KEEP_DAYS = 14

# Primary first. Sunshine Coast Airport is ~4 km from Twin Waters.
STATIONS = [
    {"id": "040861", "wmo": "94569", "dwo": "IDCJDW4081", "name": "Sunshine Coast Airport"},
    {"id": "040988", "wmo": "95572", "dwo": "IDCJDW4091", "name": "Nambour"},
]


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_obs(raw):
    """-> issued, {wmo: {...}} for our stations from IDQ60920.xml."""
    root = ET.fromstring(raw)
    issued = root.findtext("./amoc/issue-time-local") or root.findtext("./amoc/issue-time-utc")
    want = {s["wmo"] for s in STATIONS}
    out = {}
    for st in root.iter("station"):
        wmo = st.get("wmo-id")
        if wmo not in want:
            continue
        per = st.find("period")
        if per is None:
            continue
        rec = {"time": per.get("time-local"), "lat": num(st.get("lat")), "lon": num(st.get("lon")),
               "stn_name": st.get("stn-name")}
        for e in per.iter("element"):
            t = e.get("type")
            if t in ("rainfall", "rainfall_24hr"):
                rec[t] = {"mm": num(e.text), "start": e.get("start-time-local"), "end": e.get("end-time-local")}
        out[wmo] = rec
    return issued, out


def parse_dwo(raw):
    """Daily Weather Observations CSV -> {YYYY-MM-DD: mm} (date = end of the 24 h to 9am)."""
    text = raw.decode("latin-1")
    rows = list(csv.reader(io.StringIO(text)))
    col, out = None, {}
    for r in rows:
        if col is None:
            for i, c in enumerate(r):
                if c.strip().lower().startswith("rainfall"):
                    col = i
            if col is not None and "Date" in r:
                dcol = r.index("Date")
            continue
        if len(r) <= col:
            continue
        try:
            d = dt.date.fromisoformat("-".join(f"{int(x):02d}" if i else x for i, x in enumerate(r[dcol].split("-"))))
        except (ValueError, IndexError):
            continue
        mm = num(r[col])
        if mm is not None:
            out[d.isoformat()] = mm
    return out


def load():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save(d):
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
        f.write("\n")


def r1(x):
    return None if x is None else round(x + 1e-9, 1)


def build_station(cfg, obs, old_st, now, errors):
    d_km = haversine_km(HOME["lat"], HOME["lon"], obs["lat"], obs["lon"]) if obs.get("lat") is not None else None
    since = obs.get("rainfall") or {}
    last24 = obs.get("rainfall_24hr") or {}
    if since.get("start"):
        start = dt.datetime.fromisoformat(since["start"]).astimezone(BNE)
    else:  # fall back to the current BOM rain day
        start = (now - dt.timedelta(hours=9)).replace(hour=9, minute=0, second=0)
    rain_day0 = start.date()  # completed rain days end on rain_day0, rain_day0-1, ...
    need = [(rain_day0 - dt.timedelta(days=i)).isoformat() for i in range(WEEK_DAYS - 1)]

    # daily history: previous file < DWO CSV < 10-minute feed (most authoritative last)
    daily, src = {}, {}
    for row in (old_st or {}).get("daily", []):
        if row.get("mm") is not None:
            daily[row["date"]], src[row["date"]] = row["mm"], row.get("src", "history")
    months = sorted({d[:7].replace("-", "") for d in need})
    for ym in months:
        url = DWO_CSV.format(ym=ym, dwo=cfg["dwo"])
        try:
            for k, v in parse_dwo(get(url)).items():
                daily[k], src[k] = v, "dwo"
        except Exception as e:
            errors.append(f"{cfg['name']} DWO {ym}: {str(e)[:120]}")
    if last24.get("mm") is not None and last24.get("end"):
        k = dt.datetime.fromisoformat(last24["end"]).astimezone(BNE).date().isoformat()
        daily[k], src[k] = last24["mm"], "obs"

    keep = sorted(daily)[-KEEP_DAYS:]
    missing = [k for k in need if k not in daily]
    week = (since.get("mm") or 0.0) + sum(daily[k] for k in need if k in daily)
    return {
        "id": cfg["id"], "wmo": cfg["wmo"], "name": cfg["name"], "stn_name": obs.get("stn_name"),
        "lat": obs.get("lat"), "lon": obs.get("lon"),
        "distance_km": round(d_km, 1) if d_km is not None else None,
        "obs_time": obs.get("time"),
        "today_mm": r1(since.get("mm")),
        "today_start": since.get("start") or start.isoformat(),
        "today_end": since.get("end") or obs.get("time"),
        "last_day_mm": r1(last24.get("mm")),
        "last_day_end": last24.get("end"),
        "week_mm": r1(week) if since.get("mm") is not None else None,
        "week_start": (start - dt.timedelta(days=WEEK_DAYS - 1)).isoformat(),
        "week_days_missing": missing,
        "daily": [{"date": k, "mm": daily[k], "src": src[k]} for k in keep],
        "obs_url": OBS_PAGE.format(wmo=cfg["wmo"]),
        "dwo_url": DWO_PAGE.format(dwo=cfg["dwo"]),
    }


def main():
    now = dt.datetime.now(BNE).replace(microsecond=0)
    old = load()
    try:
        issued, obs = parse_obs(get(SRC))
        if not obs:
            raise ValueError("no rainfall stations found in IDQ60920")
    except Exception as e:
        print(f"WARN: rain fetch failed: {e}", file=sys.stderr)
        if old and not old.get("stale"):
            old.update(stale=True, stale_since=now.isoformat(), stale_reason=str(e)[:200])
            save(old)
        return 0
    olds = {s.get("wmo"): s for s in (old or {}).get("stations", [])}
    errors, stations = [], []
    for cfg in STATIONS:
        if cfg["wmo"] in obs:
            stations.append(build_station(cfg, obs[cfg["wmo"]], olds.get(cfg["wmo"]), now, errors))
        elif cfg["wmo"] in olds:  # station dropped out of the feed: keep its last copy, flagged
            stations.append(dict(olds[cfg["wmo"]], stale=True))
    data = {
        "generated_at": now.isoformat(),
        "stale": False,
        "issued": issued,
        "source_url": SRC,
        "page_url": "https://www.bom.gov.au/qld/observations/seqld.shtml",
        "attribution": f"Rainfall observations \u00a9 Commonwealth of Australia {now.year}, Bureau of Meteorology",
        "method": ("BOM rain day = 9am to 9am. today_mm = rain since 9am (IDQ60920). "
                   "week_mm = today_mm + the 6 completed rain days before it (24 h to 9am; "
                   "IDQ60920 rainfall_24hr + Daily Weather Observations), i.e. 7 rain days."),
        "centre": HOME, "radius_km": RADIUS_KM,
        "warnings": errors,
        "stations": stations,
    }
    strip = lambda d: {k: v for k, v in (d or {}).items() if k != "generated_at"}
    if old and strip(old) == strip(data):
        print("no change; rain.json left untouched")
    else:
        save(data)
    for s in stations:
        print(f"rain: {s['name']} since 9am {s['today_mm']} mm, 7 days {s['week_mm']} mm "
              f"(obs {s['obs_time']}, missing {s['week_days_missing']})")
    for e in errors:
        print("WARN:", e, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
