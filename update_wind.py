#!/usr/bin/env python3
"""Fetch BOM Queensland 10-minute observations (IDQ60920) and write wind.json
with the latest wind at each BOM station inside the Twin Waters circle.

Wind direction is meteorological: the direction the wind blows FROM
(BOM convention), in degrees true. Standard library only. A failed fetch keeps
the previous file (marked stale).
"""
import datetime as dt
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from update_data import HOME, RADIUS_KM, UA, haversine_km

BNE = ZoneInfo("Australia/Brisbane")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "wind.json")
SRC = "https://www.bom.gov.au/fwo/IDQ60920.xml"
PRODUCT_PAGE = "https://www.bom.gov.au/qld/observations/seqld.shtml"
OBS_PAGE = "https://www.bom.gov.au/products/IDQ60801/IDQ60801.{wmo}.shtml"


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch(timeout=60):
    req = urllib.request.Request(SRC, headers={"User-Agent": UA, "Accept": "application/xml,text/xml,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse(raw):
    root = ET.fromstring(raw)
    issued = root.findtext("./amoc/issue-time-local") or root.findtext("./amoc/issue-time-utc")
    out = []
    for st in root.iter("station"):
        lat, lon = num(st.get("lat")), num(st.get("lon"))
        if lat is None or lon is None:
            continue
        d = haversine_km(HOME["lat"], HOME["lon"], lat, lon)
        if d > RADIUS_KM:
            continue
        per = st.find("period")
        if per is None:
            continue
        el = {e.get("type"): (e.text or "").strip() for e in per.iter("element")}
        spd = num(el.get("wind_spd_kmh"))
        deg = num(el.get("wind_dir_deg"))
        compass = el.get("wind_dir") or None
        if spd is None and compass is None:
            continue  # station does not report wind
        calm = (compass or "").upper() == "CALM" or spd == 0
        if deg is None and not calm:
            continue
        wmo = st.get("wmo-id")
        out.append({
            "id": st.get("bom-id"),
            "wmo": wmo,
            "name": (st.get("description") or st.get("stn-name") or "").strip(),
            "stn_name": st.get("stn-name"),
            "lat": lat, "lon": lon,
            "distance_km": round(d, 1),
            "time": per.get("time-local"),
            "wind_dir": "CALM" if calm else compass,
            "wind_dir_deg": None if calm else deg,
            "wind_spd_kmh": spd if spd is not None else 0,
            "wind_spd_kt": num(el.get("wind_spd")),
            "gust_kmh": num(el.get("gust_kmh")),
            "max_gust_kmh": num(el.get("maximum_gust_kmh")),
            "max_gust_dir": el.get("maximum_gust_dir"),
            "url": OBS_PAGE.format(wmo=wmo) if wmo else PRODUCT_PAGE,
        })
    out.sort(key=lambda s: s["distance_km"])
    return issued, out


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


def main():
    now = dt.datetime.now(BNE).replace(microsecond=0)
    try:
        issued, stations = parse(fetch())
    except Exception as e:
        print(f"WARN: wind fetch failed: {e}", file=sys.stderr)
        old = load()
        if old and not old.get("stale"):
            old.update(stale=True, stale_since=now.isoformat(), stale_reason=str(e)[:200])
            save(old)
        return 0
    data = {
        "generated_at": now.isoformat(),
        "stale": False,
        "issued": issued,
        "source_url": SRC,
        "page_url": PRODUCT_PAGE,
        "attribution": f"Wind observations © Commonwealth of Australia {now.year}, Bureau of Meteorology",
        "convention": "wind_dir / wind_dir_deg = direction the wind blows FROM (degrees true)",
        "centre": HOME, "radius_km": RADIUS_KM,
        "count": len(stations),
        "stations": stations,
    }
    old = load()
    strip = lambda d: {k: v for k, v in (d or {}).items() if k != "generated_at"}
    if old and strip(old) == strip(data):
        print("no change; wind.json left untouched")
    else:
        save(data)
    print(f"wind: {len(stations)} stations in circle: " +
          ", ".join(f"{s['name']} {s['wind_dir']} {s['wind_spd_kmh']:.0f} km/h" for s in stations))
    return 0


if __name__ == "__main__":
    sys.exit(main())
