#!/usr/bin/env python3
"""Twin Waters Info: BOM tide predictions for Mooloolaba -> tides.json.

Source: the BOM tide-predictions print page for Mooloolaba (location
QLD_TP019), 7 days from today (Brisbane date). Each high/low has a
machine-readable data-time-local attribute and a height cell, so parsing is
simple. If that fails, the getNextTides JSON (next high + next low only) is
used instead. The browser picks "next high / next low" from the list itself,
so the file only changes once a day.

Standard library only. A failed fetch keeps the previous file (marked stale).

Tide predictions (c) Commonwealth of Australia, Bureau of Meteorology. BOM's
Tidal Information Conditions of Use require the copyright acknowledgement and
disclaimer below to be shown with any publication of the predictions.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from update_data import UA

HERE = os.path.dirname(os.path.abspath(__file__))
TIDES_FILE = os.path.join(HERE, "tides.json")
BNE = ZoneInfo("Australia/Brisbane")
AAC = "QLD_TP019"
NAME = "Mooloolaba"
DAYS = 7
PRINT_URL = ("https://www.bom.gov.au/australia/tides/print.php?aac={aac}&type=tide&date={date}"
             "&region=QLD&tz=Australia/Brisbane&tz_js=AEST&days={days}")
NEXT_URL = ("https://www.bom.gov.au/australia/tides/scripts/getNextTides.php?aac={aac}"
            "&offset=false&tz=Australia%2FBrisbane")
TIDES_PAGE = "https://www.bom.gov.au/australia/tides/"
CONDITIONS_URL = "https://www.bom.gov.au/oceanography/projects/ntc/Tidal_Information_Conditions_of_Use.pdf"
ATTRIBUTION = "Tide predictions \u00a9 Commonwealth of Australia {year}, Bureau of Meteorology"
DISCLAIMER = ("The Bureau of Meteorology gives no representation or warranty of any kind whether express, "
              "implied, statutory or otherwise in respect to the availability, accuracy, currency, completeness, "
              "quality, reliability or suitability of the information or that the information will be fit for "
              "any particular purpose or will not infringe any third party Intellectual Property rights. The "
              "Bureau's liability for any loss, damage, cost or expense resulting from use of, or reliance on, "
              "the information is entirely excluded.")

ROW = re.compile(r'data-time-local="([^"]+)"\s+class="localtime (high|low)-tide"[^>]*>.*?'
                 r'class="height (?:high|low)-tide"[^>]*>\s*(-?[\d.]+)\s*m', re.S)


def fetch(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": TIDES_PAGE})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def from_print(today):
    url = PRINT_URL.format(aac=AAC, date=today.strftime("%d-%m-%Y"), days=DAYS)
    page = fetch(url)
    if NAME.lower() not in page.lower():
        raise ValueError("page does not mention " + NAME)
    out = []
    for t, kind, h in ROW.findall(page):
        when = dt.datetime.fromisoformat(t).astimezone(BNE)
        out.append({"time": when.isoformat(timespec="minutes"), "type": kind, "height_m": round(float(h), 2)})
    if len(out) < DAYS * 3:
        raise ValueError(f"only {len(out)} tides parsed")
    return out, url


def from_next():
    d = json.loads(fetch(NEXT_URL.format(aac=AAC)))["results"]
    out = []
    for kind in ("high", "low"):
        x = d.get("next_" + kind) or {}
        if x.get("time"):
            when = dt.datetime.fromtimestamp(int(x["time"]), BNE)
            out.append({"time": when.isoformat(timespec="minutes"), "type": kind, "height_m": float(x["height"])})
    if not out:
        raise ValueError("no next tides in response")
    out.sort(key=lambda r: r["time"])
    return out, NEXT_URL.format(aac=AAC)


def load():
    try:
        with open(TIDES_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def strip(d):
    return {k: v for k, v in (d or {}).items() if not k.startswith("generated_at")}


def main():
    now = dt.datetime.now(BNE)
    old = load()
    errors, preds, url, method = [], None, None, None
    for method, fn in (("print", lambda: from_print(now.date())), ("next", from_next)):
        try:
            preds, url = fn()
            break
        except Exception as e:  # noqa: BLE001
            errors.append(f"{method}: {type(e).__name__}: {e}")
            print("WARN: tides " + errors[-1], file=sys.stderr)
    if preds is None:
        if old and not old.get("stale"):
            old.update(stale=True, stale_since=now.isoformat(timespec="seconds"), stale_reason="; ".join(errors))
            with open(TIDES_FILE, "w") as f:
                json.dump(old, f, indent=1, ensure_ascii=False)
                f.write("\n")
        raise SystemExit("tide predictions unavailable; previous tides.json kept")
    data = {
        "generated_at": now.isoformat(timespec="seconds"),
        "generated_at_text": now.strftime("%a %d %b %Y %I:%M %p AEST"),
        "stale": False,
        "location": NAME, "aac": AAC, "lat": -26.6842, "lon": 153.1331,
        "gauge_name": "Mooloolaba Tide",
        "method": method,
        "source_url": url,
        "page_url": TIDES_PAGE,
        "attribution": ATTRIBUTION.format(year=now.year),
        "disclaimer": DISCLAIMER,
        "conditions_url": CONDITIONS_URL,
        "note": "Astronomical predictions only (no weather, storm-surge or flood effects). Times AEST. "
                "Heights in metres on the BOM tide-table datum, which may differ from the live gauge datum.",
        "predictions": preds,
    }
    if old is not None and strip(old) == strip(data):
        print("no change; tides.json left untouched")
        return
    with open(TIDES_FILE, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"wrote tides.json: {len(preds)} predictions via {method}")


if __name__ == "__main__":
    main()
