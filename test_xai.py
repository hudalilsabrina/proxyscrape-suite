"""Uji: apakah proxy 'berguna' bisa capai accounts.x.ai? (relevan utk grok-suite)"""
import json, sys, urllib.request, concurrent.futures as cf
sys.path.insert(0, "/root/proxyscrape-suite")

alive = json.load(open("/root/proxyscrape-suite/data/alive.json"))
useful = [p for p in alive if not p.get("transparent")]
print(f"proxy berguna: {len(useful)}")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def reach(p):
    if p["proto"] != "http":
        return None
    host, port = p["host"], p["port"]
    try:
        op = urllib.request.build_opener(urllib.request.ProxyHandler(
            {"http": f"http://{host}:{port}", "https": f"http://{host}:{port}"}))
        req = urllib.request.Request("https://accounts.x.ai/sign-up?redirect=grok-com",
                                     headers={"User-Agent": UA})
        r = op.open(req, timeout=15)
        return {**p, "xai_status": r.status}
    except urllib.error.HTTPError as e:
        return {**p, "xai_status": e.code}
    except Exception:
        return None

http_ones = [p for p in useful if p["proto"] == "http"][:80]
print(f"menguji {len(http_ones)} proxy http -> accounts.x.ai ...")
ok = []
with cf.ThreadPoolExecutor(max_workers=30) as ex:
    for r in ex.map(reach, http_ones):
        if r and r.get("xai_status") in (200, 403):
            ok.append(r)
print(f"\nbisa capai accounts.x.ai: {len(ok)}")
for r in ok[:15]:
    print(f"  {r['raw']:<42} status={r['xai_status']} egress={r.get('egress','')[:20]}")
json.dump(ok, open("/root/proxyscrape-suite/data/proxies_xai.json", "w"), indent=1)
