"""Fetcher + checker proxy.

fetch_all()      : ambil dari semua sumber, parse, dedupe.
check_one()      : tes 1 proxy (TCP + HTTP GET ke endpoint echo-IP).
check_many()     : cek paralel dengan ThreadPool, simpan yang hidup.
"""
import concurrent.futures as cf
import json
import socket
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from .sources import SOURCES, parse

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
ECHO = "http://httpbin.org/ip"   # endpoint untuk cek egress IP


def fetch_source(src: Dict[str, str], timeout: int = 25) -> List[Dict[str, str]]:
    req = urllib.request.Request(src["url"], headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception:
        return []
    return parse(src["name"], src["kind"], src["fmt"], text)


def fetch_all(sources: Optional[List[Dict]] = None, workers: int = 10,
              verbose: bool = True) -> List[Dict[str, str]]:
    """Ambil dari semua sumber secara paralel, dedupe by host:port:proto."""
    srcs = sources or SOURCES
    out: List[Dict[str, str]] = []
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_source, s): s for s in srcs}
        for f in cf.as_completed(futs):
            s = futs[f]
            try:
                items = f.result()
            except Exception:
                items = []
            if verbose:
                print(f"  [{s['name']:<24}] {len(items)} proxy")
            out.extend(items)
    # dedupe
    seen = set()
    uniq = []
    for p in out:
        k = f"{p['proto']}://{p['host']}:{p['port']}"
        if k in seen:
            continue
        seen.add(k)
        uniq.append(p)
    if verbose:
        print(f"  TOTAL unik: {len(uniq)}")
    return uniq


def check_one(p: Dict[str, str], timeout: int = 12, echo: str = ECHO) -> Optional[Dict]:
    """Tes 1 proxy: HTTP GET ke echo endpoint. Return dict hasil atau None."""
    host, port, proto = p["host"], p["port"], p["proto"]
    t0 = time.time()
    # 1. TCP connect dulu (cepat, filter mati)
    try:
        s = socket.create_connection((host, int(port)), timeout=min(timeout, 8))
        s.close()
    except Exception as e:
        return None
    tcp_ms = round((time.time() - t0) * 1000)
    # 2. HTTP via proxy (hanya http/socks didukung urllib utk http; socks perlu PySocks)
    url = f"{proto}://{host}:{port}"
    try:
        if proto in ("socks4", "socks5"):
            # coba pakai socks via PySocks kalau ada
            try:
                import socks  # PySocks
                st = socks.socksocket()
                st.set_proxy(socks.SOCKS5 if proto == "socks5" else socks.SOCKS4, host, int(port))
                st.settimeout(timeout)
                st.connect(("httpbin.org", 80))
                st.sendall(b"GET /ip HTTP/1.1\r\nHost: httpbin.org\r\nConnection: close\r\n\r\n")
                data = st.recv(4096).decode("utf-8", "replace")
                st.close()
                import re
                m = re.search(r'"origin"\s*:\s*"([^"]+)"', data)
                egress = m.group(1) if m else None
                if egress:
                    return {**p, "tcp_ms": tcp_ms, "ms": round((time.time() - t0) * 1000), "egress": egress}
                return None
            except ImportError:
                return None
        # http
        if p.get("user"):
            # proxy auth -> handler dengan kredensial di URL
            proxy_url = f"http://{p['user']}:{p['password']}@{host}:{port}"
        else:
            proxy_url = f"http://{host}:{port}"
        op = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url}))
        r = op.open(urllib.request.Request(echo, headers={"User-Agent": _UA}), timeout=timeout)
        body = r.read().decode("utf-8", "replace")
        import re
        m = re.search(r'"origin"\s*:\s*"([^"]+)"', body)
        egress = m.group(1) if m else None
        if egress:
            return {**p, "tcp_ms": tcp_ms, "ms": round((time.time() - t0) * 1000), "egress": egress}
        return None
    except Exception:
        return None


def get_public_ip(timeout: int = 10) -> Optional[str]:
    """IP publik kita sendiri (untuk deteksi proxy transparan)."""
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": _UA}), timeout=timeout) as r:
                return r.read().decode().strip()
        except Exception:
            continue
    return None


def mark_transparent(alive: List[Dict], my_ip: Optional[str]) -> List[Dict]:
    """Tandai proxy yang egress-nya == IP kita (transparan / tak ganti IP)."""
    if not my_ip:
        return alive
    for p in alive:
        eg = (p.get("egress") or "").split(",")
        eg = [e.strip() for e in eg]
        p["transparent"] = my_ip in eg
    return alive


def check_many(proxies: List[Dict], workers: int = 200, timeout: int = 12,
               verbose: bool = True) -> List[Dict]:
    """Cek banyak proxy paralel. Return yang hidup (bisa HTTP lewat proxy)."""
    alive: List[Dict] = []
    done = 0
    total = len(proxies)
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(check_one, p, timeout): p for p in proxies}
        for f in cf.as_completed(futs):
            done += 1
            try:
                r = f.result()
            except Exception:
                r = None
            if r:
                alive.append(r)
                if verbose:
                    print(f"  OK {r['raw']:<45} egress={r.get('egress')} {r.get('ms')}ms", flush=True)
            if verbose and done % 500 == 0:
                print(f"  ... {done}/{total} dicek, {len(alive)} hidup", flush=True)
    return alive
