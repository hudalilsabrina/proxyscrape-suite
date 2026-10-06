"""Registry sumber proxy publik gratis.

Setiap sumber: {name, url, kind, fmt}
  kind : http | socks4 | socks5 | mixed
  fmt  : ipport | ipport_user | json | geonode
"""
import json
import re
from typing import Dict, List

SOURCES: List[Dict[str, str]] = [
    # --- ProxyScrape ---
    {"name": "proxyscrape_v2_http", "url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all", "kind": "http", "fmt": "ipport"},
    {"name": "proxyscrape_v2_socks4", "url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=10000&country=all", "kind": "socks4", "fmt": "ipport"},
    {"name": "proxyscrape_v2_socks5", "url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all", "kind": "socks5", "fmt": "ipport"},
    {"name": "proxyscrape_v4_http", "url": "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&proxy_format=ipport&format=text", "kind": "http", "fmt": "ipport"},
    {"name": "proxyscrape_v4_socks5", "url": "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=socks5&proxy_format=ipport&format=text", "kind": "socks5", "fmt": "ipport"},
    {"name": "proxyscrape_v4_json", "url": "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&proxy_format=protocolipport&format=json", "kind": "http", "fmt": "json_proxyscrape"},
    # --- GitHub lists ---
    {"name": "speedx_http", "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt", "kind": "http", "fmt": "ipport"},
    {"name": "speedx_socks4", "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt", "kind": "socks4", "fmt": "ipport"},
    {"name": "speedx_socks5", "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt", "kind": "socks5", "fmt": "ipport"},
    {"name": "monosans_http", "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt", "kind": "http", "fmt": "ipport_or_user"},
    {"name": "monosans_socks4", "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt", "kind": "socks4", "fmt": "ipport_or_user"},
    {"name": "monosans_socks5", "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt", "kind": "socks5", "fmt": "ipport_or_user"},
    {"name": "clarketm_raw", "url": "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt", "kind": "http", "fmt": "ipport"},
    {"name": "shiftytr_http", "url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt", "kind": "http", "fmt": "ipport"},
    {"name": "shiftytr_socks5", "url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt", "kind": "socks5", "fmt": "ipport"},
    {"name": "roosterkid_https", "url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt", "kind": "http", "fmt": "ipport"},
    {"name": "hookzof_socks5", "url": "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt", "kind": "socks5", "fmt": "ipport"},
    {"name": "jetkai_http", "url": "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt", "kind": "http", "fmt": "ipport"},
    {"name": "proxifly_all", "url": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt", "kind": "mixed", "fmt": "url"},
    # --- API JSON ---
    {"name": "geonode", "url": "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc", "kind": "mixed", "fmt": "geonode"},
    {"name": "openproxylist_http", "url": "https://api.openproxylist.xyz/http.txt", "kind": "http", "fmt": "ipport"},
]


def parse(name: str, kind: str, fmt: str, text: str) -> List[Dict[str, str]]:
    """Parse isi sumber -> list {proto, host, port, user, password, raw}."""
    out: List[Dict[str, str]] = []

    def add(proto, ipport, user=None, pw=None):
        ipport = ipport.strip()
        if not re.match(r"^\d{1,3}(\.\d{1,3}){3}:\d{1,5}$", ipport):
            return
        host, port = ipport.rsplit(":", 1)
        out.append({"proto": proto, "host": host, "port": port,
                    "user": user or "", "password": pw or "",
                    "raw": f"{proto}://" + (f"{user}:{pw}@" if user else "") + ipport,
                    "source": name})

    if fmt == "ipport":
        for ln in text.splitlines():
            ln = ln.strip()
            if ln:
                add(kind if kind != "mixed" else "http", ln)
    elif fmt == "ipport_or_user":
        # format: ip:port  ATAU  user:pass@ip:port
        for ln in text.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            if "@" in ln:
                cred, ipport = ln.split("@", 1)
                if ":" in cred:
                    u, p = cred.split(":", 1)
                    add(kind, ipport, u, p)
            else:
                add(kind, ln)
    elif fmt == "url":
        # format: proto://[user:pass@]ip:port
        for ln in text.splitlines():
            ln = ln.strip()
            m = re.match(r"^(http|https|socks4|socks5)://(?:([^:@/]+):([^@/]+)@)?(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})$", ln)
            if m:
                proto, u, p, host, port = m.groups()
                proto = "http" if proto in ("http", "https") else proto
                out.append({"proto": proto, "host": host, "port": port,
                            "user": u or "", "password": p or "",
                            "raw": ln, "source": name})
    elif fmt == "geonode":
        try:
            d = json.loads(text)
            for it in d.get("data", []):
                proto = (it.get("protocols") or ["http"])[0]
                if proto == "https":
                    proto = "http"
                add(proto, f"{it.get('ip')}:{it.get('port')}")
        except Exception:
            pass
    elif fmt == "json_proxyscrape":
        try:
            d = json.loads(text)
            items = d.get("proxies", d if isinstance(d, list) else [])
            for it in items:
                if isinstance(it, dict):
                    add(it.get("protocol", kind), f"{it.get('ip')}:{it.get('port')}")
                elif isinstance(it, str):
                    m = re.match(r"^(http|socks4|socks5)://(.+:\d+)$", it)
                    if m:
                        add(m.group(1), m.group(2))
        except Exception:
            pass

    return out
