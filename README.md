# Twin Waters Info

**Live map: https://alanjhaase-lang.github.io/sunshine-coast-flood-map/**

A self-updating static web map (Leaflet + OpenStreetMap) of Bureau of Meteorology
river-height gauges, a Mooloolaba coastal tide card, QLDTraffic flood road closures, roadworks, hazards,
crashes and flood cameras, and rain radar for the
Twin Waters on the Sunshine Coast, Queensland. A Twin Waters–centred spin-off of the
[Westbrook flood map](https://github.com/alanjhaase-lang/westbrook-flood-map).

> **Disclaimer:** Unofficial community map. Data from the Bureau of Meteorology may be delayed or
> contain faulty readings. Do not rely on it for safety decisions. Check
> [BOM warnings (bom.gov.au)](https://www.bom.gov.au/qld/warnings/), your council disaster dashboard
> ([Sunshine Coast Council disaster hub](https://disasterhub.sunshinecoast.qld.gov.au/)),
> and call SES 132 500 or 000 in an emergency.
>
> The map shows this as a short line in the header panel and as a notice on first visit
> (dismissal remembered in `localStorage` key `twinfo.disclaimer.v1`; the *more* link reopens it).

## Area

One great-circle circle (`HOME`, `RADIUS_KM` and `REGIONS` in `update_data.py`):

| Area | Centre | Radius | Covers |
|---|---|---|---|
| Twin Waters (`twinwaters`) | -26.6336, 153.0814 | 20 km | Mudjimba / Maroochydore / Pacific Paradise / Coolum approaches |

Gauges, closures and cameras are all filtered with the same circle. Each gauge in `data.json` has
`region`, `region_name`, `distance_km` (to the centre) and `distance_from`.

The map has a collapsible panel (top right; collapsed by default on phones) showing the area with
its gauge count, in-flood count and a *Zoom* button, a **Coastal tide** card, then the layers:
**River gauges** (with an *In flood only* filter), **Road closures (flooding)**, **Flood cameras**,
**Roadworks**, **Hazards**, **Crashes** and **Rain radar**.
Settings persist in `localStorage` under `twinfo.*` keys (separate from the Westbrook map).

### Gauges approaching the next flood class (flashing markers)

A gauge with a current reading and official flood levels that is within **0.2 m** of its next class
(`0 < delta_m <= 0.2` in `data.json`) pulses between its current colour and the next class colour:
green↔yellow (below flood level, approaching Minor), yellow↔orange (Minor, approaching Moderate) and
orange↔red (Moderate, approaching Major). The popup and the tide card say *Approaching …*. Gauges with
no levels, no reading, or more than 0.2 m to go do not flash. With `prefers-reduced-motion` the marker
shows a static half/half colour instead. `NEAR_NEXT_M` in `index.html` sets the threshold.

### Coastal tide card

The panel shows the tide as a compact one-line chip, e.g. `🌊 Tide 1.74 m ↑ · L 1:16pm 0.3 · H 7:11pm 1.6 ▾`
(⚠ is added when the gauge is in flood or near the next class). Click it to expand the details;
open/closed persists as `twinfo.tideOpen.v1` (collapsed by default). Expanded, it shows:

- the live BOM **Mooloolaba Tide** gauge from `data.json` (height, tendency arrow, reading time, datum,
  distance to Minor, and a warning when it is in flood or within 0.2 m of the next class);
- the **next high and next low** (time AEST and predicted height) for Mooloolaba from `tides.json`.
  `update_tides.py` (stdlib) fetches 7 days of BOM tide predictions (location `QLD_TP019`) from the BOM
  tide-predictions print page, which carries machine-readable `data-time-local` attributes; if that
  fails it falls back to BOM's `getNextTides.php` JSON (next high/low only). The browser picks the next
  high/low from the list, so the file only changes once a day and still works if a run is missed;
- a *Show gauge* button (zooms to the gauge and opens its popup, which also lists next high/low), links
  to the BOM tide table, the [Sunshine Coast waters forecast](https://www.bom.gov.au/qld/forecasts/sunshine-coast-waters.shtml)
  and the gauge plot;
- a one-line storm tide / coastal inundation note pointing to [BOM warnings](https://www.bom.gov.au/qld/warnings/)
  and the [Sunshine Coast Disaster Hub](https://disaster.sunshinecoast.qld.gov.au/). No storm-surge heights
  are shown or estimated.

Predictions are astronomical only (no wind, surge or flood effects) and use the BOM tide-table datum,
which may differ from the gauge datum (LGH). Per BOM's
[Tidal Information Conditions of Use](https://www.bom.gov.au/oceanography/projects/ntc/Tidal_Information_Conditions_of_Use.pdf),
the card shows "Tide predictions © Commonwealth of Australia, Bureau of Meteorology" and a *disclaimer*
link that expands BOM's required disclaimer text (also stored in `tides.json`).

All standing credits and disclaimers (BOM, tide copyright + disclaimer, QLDTraffic CC BY 4.0,
RainViewer, OSM, the "not for safety decisions" line) sit at the **bottom of the panel**; the
first-visit notice is still shown once and can be dismissed.

### Wind arrows

The **Wind (BOM)** layer (on by default; persisted as `twinfo.wind.v1`) draws an arrow at each BOM
automatic weather station inside the 20 km circle that reports wind (currently Sunshine Coast Airport
and Nambour). `update_wind.py` (stdlib) reads the official BOM Queensland 10-minute observations
product [IDQ60920](https://www.bom.gov.au/fwo/IDQ60920.xml) and writes `wind.json` (speed km/h and
knots, gust, max gust today, direction, observation time).

- BOM direction is meteorological: where the wind blows **from**. Popups say e.g. "from NE (45°)".
- The arrow is drawn flying **downwind** (the way the air moves, i.e. direction + 180°), like a
  streamline; the number in the middle is the speed in km/h. A circle means calm.
- Colour and length scale with speed: grey <5, green 5–19, yellow 20–29, orange 30–39,
  red 40–61, purple 62+ km/h.
- Attribution: "Wind observations © Commonwealth of Australia, Bureau of Meteorology", with a
  link to the station's BOM observations page. Live Wind (live-wind.com.au) is linked only as an
  optional "more wind maps" link; none of its data is used or copied.
- Data are as fresh as the last workflow run (≈30 min) plus BOM's 10-minute obs cycle.

### Rain radar overlay

The panel also has a **Rain radar** checkbox (off by default; on/off and opacity persist in
`localStorage`). When on it shows the latest frame of the free
[RainViewer Weather Maps API](https://www.rainviewer.com/api/weather-maps-api.html)
(`https://api.rainviewer.com/public/weather-maps.json`), with an opacity slider (default 0.6),
a ▶/⏸ button that loops the past ~2 hours (13 frames, 10-minute steps) and the frame time in
Brisbane time (AEST). The frame list refreshes every 5 minutes along with `data.json`.
Radar tiles sit in their own pane (z-index 350) above the base map but below the area
circle and gauge markers.

RainViewer free-tier limits (since 1 Jan 2026): personal/educational use only, attribution
link to rainviewer.com required (shown in the map attribution), past frames only (no
nowcast), one colour scheme (Universal Blue, scale shown in the panel), max tile zoom 7
(the map upscales z7 tiles when zoomed in, so radar looks blocky at street level) and
100 requests/IP/minute. Availability is not guaranteed.

### Road closures (flooding) and flood cameras

Two more panel checkboxes, both from [QLDTraffic](https://qldtraffic.qld.gov.au/)
(Road data © State of Queensland (QLDTraffic), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
shown in the map attribution). On/off persists in `localStorage` (`twinfo.closures.v1`, default on;
`twinfo.cameras.v1`, default off). Only items with a vertex inside the Twin Waters circle are
kept. They are **not** hidden by *In flood only*, which applies to gauges only.

- **Road closures** – `closures.json`, built by `update_roads.py` from QLDTraffic events. Source order:
  the official API `https://api.qldtraffic.qld.gov.au/v2/events` with the shared public key from the
  [API spec v1.10](https://qldtraffic.qld.gov.au/media/moreDevelopers-and-Data/qldtraffic-website-api-specification-v1-10.pdf)
  (often HTTP 429 because everyone shares it), falling back to the static feed
  `https://data.qldtraffic.qld.gov.au/events_v2.geojson` (same structure, updated every minute).
  `source.used` records `api` or `fallback`. Kept: `event_type == "Flooding"` or `event_due_to`
  containing "flood" (this includes *Road damage – earlier flooding* hazards), with any vertex inside the
  Twin Waters circle. Dropped (listed in `excluded` with a reason): any vertex outside a Queensland bounding
  box, implausible road names (non-ASCII/garbage, e.g. a bad reverse geocode), status other than
  Published, or an end time in the past. `severity` is `closed` (road closed to all/through traffic,
  all lanes blocked) or `partial` (lanes affected, 4WD-only, partial closures). Drawn as a red
  "no entry" marker plus solid red line (closed) or amber diamond plus dashed amber line (partial);
  popups show road, locality/LGA, impact, cause, advice, start and last-updated time (AEST) and a
  link to qldtraffic.qld.gov.au. Coordinates in `closures.json` are `[lat, lon]`
  (`marker`, `geometry.points`, `geometry.lines`).
- **Flood cameras** – `cameras.json`, from `https://data.qldtraffic.qld.gov.au/floodcameras.geojson`
  filtered to the Twin Waters circle. The popup loads the **live** image straight from `cameras.qldtraffic.qld.gov.au`
  (https, S3/CloudFront, no hotlink protection) with a `?t=<now>` cache-buster each time it opens; if the
  image fails it shows a link instead. The image server sends no CORS headers, so the browser cannot read
  the image time; instead the update job HEADs each image and, only when it is older than 3 h, records
  `image_time` / `image_stale` (shown in the popup, grey icon). Recording a fresh time would change the
  file, and so commit, every run. Many TMR cameras only update 6am–6pm.

- **Roadworks / Hazards / Crashes** – `roadworks.json`, `hazards.json`, `crashes.json`, built by
  `update_roads.py` from the same events fetch and the same rules as closures (circle, Queensland bbox,
  plausible road name, Published, not ended, duplicate ids dropped), keeping `event_type` `Roadworks`,
  `Hazard` or `Crash`. Flood-related events stay in `closures.json` only. Each file has `generated_at`,
  `attribution` (CC BY 4.0), `count`, `regions`, `excluded` and a list under the layer name with the
  closures fields plus `end` and `priority`. Icons: orange cone (roadworks), amber warning diamond
  (hazard), red ✕ (crash); lines in the same colour, solid when closed, dashed otherwise. Events that
  have not started yet are faded and counted as *upcoming*. All three default **on**
  (`twinfo.roadworks.v1`, `twinfo.hazards.v1`, `twinfo.crashes.v1`).

On a fetch failure the previous file is kept with `stale: true`, `stale_since` and `stale_reason`
(the panel shows a warning). Like `data.json`, the files are only rewritten when something other than
`generated_at*` or the `source` block (feed timestamp, API vs fallback) changes. The map re-fetches them
every 5 minutes with `data.json`.

BOM radar is not used: BOM radar images are restricted content that needs a data licence to
republish, and BOM's radar WMS (GIS2Web) is registered-user only.

- `update_data.py` – stdlib-only Python 3.9+ script. Fetches the BOM river height
  bulletins, parses every row, joins coordinates from `stations.json`, keeps
  gauges inside the Twin Waters circle and writes `data.json` (timestamp in Australia/Brisbane).
  If only the timestamp would change, `data.json` is left untouched so the
  workflow doesn't make empty commits.
- `stations.json` – cached station-number → lat/lon lookup. New station numbers
  that appear in a bulletin are looked up automatically (BOM sources only) and
  added.
- `flood_levels.json` – cached official flood classification levels (see above);
  `build_flood_levels.py` rebuilds it.
- `build_stations.py` – one-off rebuild of `stations.json` across candidate
  bulletins, including a flagged Nominatim geocode fallback.
- `update_roads.py` – stdlib-only; writes `closures.json`, `roadworks.json`, `hazards.json`,
  `crashes.json` and `cameras.json` from QLDTraffic (see above). Imports `REGIONS` from `update_data.py`.
- `update_tides.py` – stdlib-only; writes `tides.json` (Mooloolaba tide predictions, see *Coastal tide card*).
- `update_wind.py` – stdlib-only; writes `wind.json` (BOM wind observations, see *Wind arrows*).
- `index.html` – the map. Re-fetches `data.json`, the QLDTraffic files, `tides.json`, `wind.json` (and the radar
  frame list) every 5 minutes.
- `.github/workflows/update.yml` – runs every 30 minutes (and manually), runs both scripts (the road
  step runs even if the BOM step fails) and commits the data files when they change.

### Flood levels and "metres to next class"

Clicking a gauge shows, under *Flood class*, a **Next** line such as
`Minor at 1.70 m, 0.66 m to go` (or `None — above Major by 3.03 m`) and the gauge's official
**Minor / Moderate / Major** levels with the current class highlighted. Gauges for which BOM
publishes no classification show *No official flood levels for this gauge*. The marker hover
tooltip also shows the "Next: …" text. (The popup no longer shows station number, station type,
crossing or region; those fields are still in `data.json`.)

- **Source**: the *Flood Classification Levels* line on each gauge's BOM river height plot page
  (`/fwo/IDQ65xxx/IDQ65xxx.<station>.plt.shtml`, the "BOM plot" link). The BOM National Flood
  Gauge Network service has no level attributes, and the Qld network index pages (section 1–6)
  list stations only. Levels are cached in `flood_levels.json` (`source_url`, `checked` date);
  official values only, `null` when BOM publishes none.
- **Datum**: BOM writes AHD levels as `Minor: 1.70 m AHD` and local gauge height (LGH) levels with no
  suffix. A level set is used only if its datum matches the bulletin's datum column for that gauge;
  otherwise the popup says the levels were not compared (`flood_levels_note`). No mismatches exist today.
- **Fields** added to each gauge in `data.json`: `flood_levels` {minor, moderate, major, datum,
  source_url}, `computed_class` (height ≥ level ⇒ that class), `next_class`, `next_level_m`,
  `delta_m` (= next_level_m − height_m, metres to go), `above_major_m`, `class_check`
  (computed class vs the bulletin's class: `agrees` / `differs (bulletin: …)`), `flood_levels_note`.
- **Updates**: `update_data.py` fetches levels for gauges with no cached entry and re-checks the
  8 oldest entries (older than 30 days) each run. `python3 build_flood_levels.py` does a full refresh.

## Data sources

Bulletins (configured in `BULLETINS` in `update_data.py`):

| Bulletin | Coverage | Why |
|---|---|---|
| [IDQ60287](https://www.bom.gov.au/fwo/IDQ60287.html) (primary) | Mooloolah, Maroochy, Noosa, Mary | Sunshine Coast and hinterland (upper Mary) |
| [IDQ60286](https://www.bom.gov.au/fwo/IDQ60286.html) | Stanley, Brisbane, Bremer, Lockyer, Pine/Caboolture | upper Stanley River gauges on the southern edge of the circle |

Wind: BOM Queensland 10-minute observations [IDQ60920](https://www.bom.gov.au/fwo/IDQ60920.xml).

Rainfall totals (`rain.json`, `update_rain.py`; side-panel chip, toggle *Rainfall totals (BOM)*,
state in localStorage `twinfo.rain.v1`): primary station **Sunshine Coast Airport** (BOM 040861,
~4 km from Twin Waters), secondary **Nambour** (BOM 040988, ~14 km).

- BOM rain day = 9am to 9am; a daily total is filed against the date its 24 h ends.
- **Today** (`today_mm`) = rain since 9am from IDQ60920 (`rainfall`). Before 9am this is still
  the previous day's rain day, and the chip says "Since 9am" instead of "Rain today".
- **7 days** (`week_mm`) = since 9am + the 6 completed rain days before it: the latest from
  IDQ60920 `rainfall_24hr`, earlier ones from BOM Daily Weather Observations CSVs
  ([IDCJDW4081](https://www.bom.gov.au/climate/dwo/IDCJDW4081.latest.shtml) Sunshine Coast Airport,
  [IDCJDW4091](https://www.bom.gov.au/climate/dwo/IDCJDW4091.latest.shtml) Nambour).
  Days already in `rain.json` are kept (rolling 14-day `daily` history), so a DWO outage does not
  lose them; days with no total are listed in `week_days_missing`.
- If IDQ60920 fails, the previous `rain.json` is kept and marked `stale`.
- Rain gauge totals only; the app does not derive flood warnings from rainfall.

Other Qld bulletins have no gauges within the 20 km circle. If a bulletin fails to download, the
previous readings for that bulletin are kept (marked `stale` in `bulletins`).

The update scripts send a browser-like `User-Agent` header (BOM returns HTTP 403 to default clients).

Coordinates, in priority order (`source` field in `stations.json`):

1. `bom_nfgn` – BOM [National Flood Gauge Network](https://hosting.wsapi.cloud.bom.gov.au/arcgis/rest/services/flood/National_Flood_Gauge_Network/FeatureServer/5) feature service, keyed by BOM station number.
2. `bom_section3` – BOM [Index of Queensland River Height Stations](https://www.bom.gov.au/qld/flood/networks/section3.shtml).
3. `geocoded_nominatim` – last-resort geocode of the place name after "at" (`geocoded: true`, approximate; popups say so).

## Updates and hosting

- Hosted on GitHub Pages from `main`, folder `/` (root):
  https://alanjhaase-lang.github.io/sunshine-coast-flood-map/
- `.github/workflows/update.yml` runs every 30 minutes (and on demand via *Run workflow*), runs
  `update_data.py`, `update_roads.py`, `update_tides.py`, `update_wind.py` and `update_rain.py`, and commits the data files when they change; Pages redeploys
  after each data commit. The map itself re-fetches the data every 5 minutes.

Note: GitHub's cron is best-effort (runs can be delayed), and scheduled workflows are
disabled automatically after 60 days without repository activity. Data commits count as
activity, but if it stops, re-enable it in the Actions tab.

## Local use

```sh
python3 update_data.py           # writes data.json
python3 update_roads.py          # writes closures/roadworks/hazards/crashes/cameras.json
python3 update_tides.py          # writes tides.json
python3 update_wind.py           # writes wind.json
python3 update_rain.py           # writes rain.json
python3 -m http.server 8000      # open http://localhost:8000/
```

Data © Commonwealth of Australia, Bureau of Meteorology. Not an official warning service —
always check [BOM warnings](https://www.bom.gov.au/qld/warnings/) in an emergency.
