#!/usr/bin/env python3
"""Daily high/low temperature for Twin Waters (temp.json).

Sources (official Bureau of Meteorology, standard library only):
  * IDQ11295.xml (QLD town precis forecasts): Maroochydore (QLD_PT002), the
      nearest BOM forecast town to Twin Waters (~4 km). Gives each day's
      forecast minimum / maximum, precis and icon. BOM drops today's minimum
      once the morning has passed (and later today's maximum), so:
  * IDQ60920.xml (QLD 10-minute observations, also used for wind/rain):
      Sunshine Coast Airport (040861, ~4 km) current temperature plus the
      running overnight minimum (6pm-9am) and daytime maximum (6am-9pm).

The frontend shows today's forecast min/max, filling a missing forecast
value with the observed one (labelled as observed). On failure of both
feeds the previous file is kept and marked stale.
"""
import datetime as dt
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from update_data import HOME, UA, haversine_km

BNE = ZoneInfo("Australia/Brisbane")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "temp.json")
FC_SRC = "https://www.bom.gov.au/fwo/IDQ11295.xml"
OBS_SRC = "https://www.bom.gov.au/fwo/IDQ60920.xml"
FC_AAC, FC_NAME = "QLD_PT002", "Maroochydore"
FC_PAGE = "https://www.bom.gov.au/places/qld/maroochydore/forecast/"
OBS = {"id": "040861", "wmo": "94569", "name": "Sunshine Coast Airport"}
OBS_PAGE = "https://www.bom.gov.au/products/IDQ60801/IDQ60801.94569.shtml"
DAYS = 4


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_forecast(raw):
    root = ET.fromstring(raw)
    issued = root.findtext("./amoc/issue-time-local")
    for a in root.iter("area"):
        if a.get("aac") != FC_AAC:
            continue
        days = []
        for p in a.findall("forecast-period")[:DAYS]:
            el = {e.get("type"): (e.text or "").strip() for e in p}
            mn, mx = num(el.get("air_temperature_minimum")), num(el.get("air_temperature_maximum"))
            days.append({
                "date": (p.get("start-time-local") or "")[:10],
                "min": None if mn is None else int(mn),
                "max": None if mx is None else int(mx),
                "precis": el.get("precis"),
                "icon": num(el.get("forecast_icon_code")),
                "pop": el.get("probability_of_precipitation"),
            })
        return issued, {"aac": FC_AAC, "name": a.get("description", FC_NAME).replace(" location", ""), "days": days}
    raise ValueError(f"{FC_AAC} not found in IDQ11295")


def parse_obs(raw):
    root = ET.fromstring(raw)
    for st in root.iter("station"):
        if st.get("wmo-id") != OBS["wmo"]:
            continue
        per = st.find("period")
        if per is None:
            break
        rec = {"id": OBS["id"], "wmo": OBS["wmo"], "name": OBS["name"], "obs_time": per.get("time-local"),
               "lat": num(st.get("lat")), "lon": num(st.get("lon")), "url": OBS_PAGE}
        if rec["lat"] is not None:
            rec["distance_km"] = round(haversine_km(HOME["lat"], HOME["lon"], rec["lat"], rec["lon"]), 1)
        for e in per.iter("element"):
            t = e.get("type")
            if t == "air_temperature":
                rec["temp"] = num(e.text)
            elif t in ("maximum_air_temperature", "minimum_air_temperature"):
                rec["max" if t.startswith("max") else "min"] = {
                    "value": num(e.text), "time": e.get("time-local"),
                    "start": e.get("start-time-local"), "end": e.get("end-time-local")}
        return rec
    raise ValueError(f"station {OBS['wmo']} not found in IDQ60920")


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
    old = load() or {}
    errors, fc, obs, issued = [], None, None, None
    try:
        issued, fc = parse_forecast(get(FC_SRC))
    except Exception as e:
        errors.append(f"forecast: {str(e)[:150]}")
    try:
        obs = parse_obs(get(OBS_SRC))
    except Exception as e:
        errors.append(f"observations: {str(e)[:150]}")
    if fc is None and obs is None:
        print("WARN: temp fetch failed: " + "; ".join(errors), file=sys.stderr)
        if old and not old.get("stale"):
            old.update(stale=True, stale_since=now.isoformat(), stale_reason="; ".join(errors)[:300])
            save(old)
        return 0
    data = {
        "generated_at": now.isoformat(),
        "stale": False,
        "forecast_issued": issued if fc else old.get("forecast_issued"),
        "forecast_stale": fc is None,
        "forecast": fc or old.get("forecast"),
        "forecast_url": FC_PAGE,
        "obs_stale": obs is None,
        "obs": obs or old.get("obs"),
        "source_urls": [FC_SRC, OBS_SRC],
        "attribution": f"Forecast and observations \u00a9 Commonwealth of Australia {now.year}, Bureau of Meteorology",
        "method": ("Daily min/max = BOM town forecast for Maroochydore (IDQ11295). BOM removes today's minimum "
                   "after the morning (and today's maximum late in the day); the frontend then uses the "
                   "Sunshine Coast Airport running observed min (6pm-9am) / max (6am-9pm) from IDQ60920, labelled."),
        "warnings": errors,
    }
    strip = lambda d: {k: v for k, v in (d or {}).items() if k != "generated_at"}
    if strip(old) == strip(data):
        print("no change; temp.json left untouched")
    else:
        save(data)
    d0 = (data["forecast"] or {}).get("days", [{}])[0] if data["forecast"] else {}
    o = data["obs"] or {}
    print(f"temp: forecast {d0.get('date')} min {d0.get('min')} max {d0.get('max')} ({d0.get('precis')}); "
          f"obs {o.get('obs_time')} now {o.get('temp')} min {(o.get('min') or {}).get('value')} "
          f"max {(o.get('max') or {}).get('value')}")
    for e in errors:
        print("WARN:", e, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
