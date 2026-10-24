# qld-flood-bom-proxy (Cloudflare Worker)

One tiny Worker shared by both community flood maps:

- Twin Waters Info – https://alanjhaase-lang.github.io/sunshine-coast-flood-map/ (`BOM_PROXY` in `../index.html`)
- Westbrook – https://alanjhaase-lang.github.io/westbrook-flood-map/ (`LIVE_PROXY` in that repo's `index.html`)

**Why:** BOM's website does not allow web pages on other sites (github.io) to read its river bulletins
(no CORS headers, 403 to cross-origin requests). This Worker fetches the bulletin from BOM on the server
side and hands it back with the right CORS header, so the maps can refresh gauge heights live every ~5 min
instead of waiting for the 15-min GitHub Actions snapshot (which stays as the backup).

## Lock list (not an open proxy)

| What | Allowed |
|---|---|
| Methods | `GET`, `HEAD`, `OPTIONS` (preflight) – others 405 |
| Origins | `https://alanjhaase-lang.github.io`, `http://localhost[:port]`, `http://127.0.0.1[:port]` – others 403 (no Origin = 403) |
| Paths | `/fwo/IDQ60285.html`, `/fwo/IDQ60286.html`, `/fwo/IDQ60287.html`, `/fwo/IDQ60293.html`, no query string – others 403 |
| Upstream | fixed `https://www.bom.gov.au` + the allowed path; redirects not followed; 2 MB cap; 10 s timeout |

Responses are cached at Cloudflare's edge for 90 s, so BOM sees at most ~1 request per bulletin per
90 s per Cloudflare location, no matter how many people have the map open.

Client usage: `fetch(BOM_PROXY + "/fwo/IDQ60287.html")`, e.g.
`https://qld-flood-bom-proxy.alanjhaase.workers.dev/fwo/IDQ60287.html`.

To add a bulletin, add its path to `ALLOWED_PATHS` in `worker.js` and redeploy.

## Free tier

Cloudflare Workers Free: 100,000 requests/day, no card needed. Each open map tab makes one request per
bulletin every 5 min (Twin Waters 2, Westbrook 4) = 576 + 1,152 requests/day per tab left open all day.
That's ~85 always-open tabs, or many thousands of normal short visits, before the cap. Over the cap
the Worker just returns errors and the maps fall back to the GitHub snapshot automatically.

## Deploy

```bash
cd bom-proxy
npx wrangler login     # once, opens browser to authorise your Cloudflare account
npx wrangler deploy    # prints https://qld-flood-bom-proxy.alanjhaase.workers.dev
```

Deployed at `https://qld-flood-bom-proxy.alanjhaase.workers.dev`. That URL (no trailing path) is set in `BOM_PROXY` (Twin Waters `index.html`) and `LIVE_PROXY`
(Westbrook `index.html`). Test:

```bash
curl -H "Origin: https://alanjhaase-lang.github.io" -I https://qld-flood-bom-proxy.alanjhaase.workers.dev/fwo/IDQ60287.html  # 200
curl -H "Origin: https://example.com" -I https://qld-flood-bom-proxy.alanjhaase.workers.dev/fwo/IDQ60287.html              # 403
```

Local test: `npx wrangler dev` (port 8787), serve the map with `python3 -m http.server`, and temporarily
set the proxy constant to `http://localhost:8787`.
