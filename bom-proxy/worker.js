// qld-flood-bom-proxy: a tiny, locked-down Cloudflare Worker that lets the two community flood maps
// (Twin Waters Info and Westbrook, both on GitHub Pages) read BOM river height bulletins live.
//
// BOM's web server does not send CORS headers (and answers 403 to cross-origin browser requests), so a
// page on github.io cannot read www.bom.gov.au directly. This Worker fetches the bulletin server-side
// and returns it with CORS headers for our own pages only.
//
// It is NOT an open proxy:
//   * only GET / HEAD / OPTIONS
//   * only the exact paths in ALLOWED_PATHS below (BOM QLD river height bulletins used by the maps)
//   * only requests whose Origin is in ALLOWED_ORIGINS (browsers always send Origin on cross-origin fetch)
//   * upstream host is fixed to https://www.bom.gov.au, the client cannot choose it
//   * responses are cached at Cloudflare's edge for CACHE_SECONDS, so many visitors = few BOM requests
// Everything else gets 403 (or 405 for other methods).
//
// Usage from a page:  fetch("https://qld-flood-bom-proxy.<account>.workers.dev/fwo/IDQ60287.html")

const UPSTREAM = "https://www.bom.gov.au";

const ALLOWED_PATHS = new Set([
  "/fwo/IDQ60285.html", // Nerang, Coomera, Pimpama, Logan-Albert, Tingalpa Creek   (Westbrook)
  "/fwo/IDQ60286.html", // Stanley, Brisbane, Bremer, Lockyer, Pine/Caboolture      (both maps)
  "/fwo/IDQ60287.html", // Mooloolah, Maroochy, Noosa, Mary                         (both maps)
  "/fwo/IDQ60293.html", // Condamine, Myall Creek, Balonne, Maranoa                 (Westbrook)
]);

const ALLOWED_ORIGINS = new Set([
  "https://alanjhaase-lang.github.io",
]);
// Local testing (python -m http.server, wrangler dev etc.): http://localhost[:port], http://127.0.0.1[:port]
const LOCAL_ORIGIN = /^http:\/\/(localhost|127\.0\.0\.1)(:\d{1,5})?$/;

const CACHE_SECONDS = 90;      // BOM updates these bulletins at most every few minutes
const UPSTREAM_TIMEOUT_MS = 10000;
const MAX_BYTES = 2_000_000;   // bulletins are ~50 KB; refuse anything absurd
// BOM returns 403 to non-browser user agents; same UA the GitHub Actions updater (update_data.py) uses.
const UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";

function originAllowed(origin) {
  return !!origin && (ALLOWED_ORIGINS.has(origin) || LOCAL_ORIGIN.test(origin));
}

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

function deny(status, msg, extra = {}) {
  return new Response(msg + "\n", {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store", "Vary": "Origin", ...extra },
  });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin");

    if (url.pathname === "/" && request.method === "GET" && !origin) {
      return deny(200, "qld-flood-bom-proxy: BOM river bulletins for alanjhaase-lang.github.io flood maps only.");
    }
    if (!originAllowed(origin)) return deny(403, "Forbidden: origin not allowed");
    if (!ALLOWED_PATHS.has(url.pathname) || url.search) return deny(403, "Forbidden: path not allowed");

    const cors = corsHeaders(origin);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (request.method !== "GET" && request.method !== "HEAD") {
      return deny(405, "Method not allowed", { ...cors, Allow: "GET, HEAD, OPTIONS" });
    }

    // Edge cache, keyed on the fixed upstream URL only (never on client headers/query).
    const upstreamUrl = UPSTREAM + url.pathname;
    const cache = caches.default;
    const cacheKey = new Request(upstreamUrl, { method: "GET" });
    let cached = await cache.match(cacheKey);
    let body, status = 200, ctype = "text/html; charset=utf-8", hit = "HIT";

    if (cached) {
      body = await cached.arrayBuffer();
      ctype = cached.headers.get("Content-Type") || ctype;
    } else {
      hit = "MISS";
      let up;
      try {
        up = await fetch(upstreamUrl, {
          method: "GET",
          headers: { "User-Agent": UA, "Accept": "text/html,*/*;q=0.8" },
          redirect: "manual",                          // never follow BOM to some other host
          signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
          cf: { cacheTtl: CACHE_SECONDS, cacheEverything: true },
        });
      } catch (e) {
        return deny(502, "Upstream fetch failed", cors);
      }
      if (up.status !== 200) return deny(502, "Upstream HTTP " + up.status, cors);
      body = await up.arrayBuffer();
      if (body.byteLength > MAX_BYTES) return deny(502, "Upstream response too large", cors);
      ctype = up.headers.get("Content-Type") || ctype;
      const toCache = new Response(body, {
        headers: { "Content-Type": ctype, "Cache-Control": `public, max-age=${CACHE_SECONDS}` },
      });
      ctx.waitUntil(cache.put(cacheKey, toCache));
    }

    return new Response(request.method === "HEAD" ? null : body, {
      status,
      headers: {
        ...cors,
        "Content-Type": ctype,
        "Cache-Control": `public, max-age=60`,
        "X-Proxy-Cache": hit,
        "X-Content-Type-Options": "nosniff",
      },
    });
  },
};
