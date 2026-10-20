"""Render the site in headless Chrome and check every <a href>.
Usage: python pipeline/check_links.py [site_url]   (default http://localhost:8787/)
Exit code 1 if any link is relative-to-nowhere or returns 4xx/5xx that isn't a known bot-check wall."""
import re, subprocess, sys, urllib.parse, requests, concurrent.futures as cf
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8787/"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
# Hosts that answer scripted requests with a Cloudflare/Radware challenge but load in a normal browser (checked by hand 2026-10-20).
BOT_WALLED = {"mvp.sos.ga.gov", "sosmt.gov", "elections.wi.gov", "www.sos.mn.gov", "www.ohiosos.gov", "www.elections.alaska.gov"}
dom = subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=10000",
                      "--dump-dom", BASE], capture_output=True, text=True, timeout=90).stdout
hrefs = sorted(set(re.findall(r'<a [^>]*href="([^"]+)"', dom)))
def check(h):
    u = urllib.parse.urljoin(BASE, h.replace("&amp;", "&"))
    try:
        r = requests.get(u, headers={"User-Agent": UA}, timeout=30, allow_redirects=True, stream=True)
        code, final = r.status_code, r.url; r.close()
    except requests.RequestException as e:
        code, final = 0, type(e).__name__
    host = urllib.parse.urlparse(u).hostname
    ok = 200 <= code < 400 or (host in BOT_WALLED and code in (0, 403))
    return ok, code, h, final if final != u else ""
with cf.ThreadPoolExecutor(8) as ex:
    res = list(ex.map(check, hrefs))
bad = [r for r in res if not r[0]]
for ok, code, h, final in res:
    print(("OK  " if ok else "BAD ") + f"{code} {h} {('-> ' + final) if final else ''}")
print(f"\n{len(res)} links checked, {len(bad)} bad")
sys.exit(1 if bad else 0)
