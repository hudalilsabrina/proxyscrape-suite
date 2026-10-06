#!/usr/bin/env python3
"""ProxyScrape Suite - agregator + validator proxy publik gratis.

Sumber: 21 endpoint (ProxyScrape v2/v4, TheSpeedX, monosans, proxifly,
geonode, openproxylist, dll). Fetch paralel -> dedupe -> cek hidup ->
simpan dalam berbagai format (txt/json/csv).

Command:
  fetch            Ambil dari semua sumber, simpan mentah
  check            Cek proxy mentah, simpan yang hidup
  update           fetch + check (satu perintah)
  list             Tampilkan ringkasan hasil
  export           Ekspor proxy hidup ke format tertentu
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.console import Console
from rich.table import Table
from rich import box

from src import fetcher
from src.sources import SOURCES

C = Console()
DATA = Path(__file__).resolve().parent / "data"
DATA.mkdir(exist_ok=True)
RAW = DATA / "raw.json"
ALIVE = DATA / "alive.json"


def _save(path, data):
    path.write_text(json.dumps(data, indent=1))


def _load(path):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return []
    return []


def cmd_fetch():
    C.print(f"[cyan]Fetch dari {len(SOURCES)} sumber...[/]")
    t0 = time.time()
    proxies = fetcher.fetch_all()
    _save(RAW, proxies)
    C.print(f"[green]{len(proxies)} proxy unik disimpan ({round(time.time()-t0)}s) -> {RAW}[/]")


def cmd_check(workers, timeout, limit, ports=None, proto=None):
    proxies = _load(RAW)
    if not proxies:
        C.print("[yellow]Belum ada data. Jalankan: ./run.sh fetch[/]")
        return
    if ports:
        want = {p.strip() for p in ports.split(",")}
        proxies = [p for p in proxies if p["port"] in want]
    if proto:
        proxies = [p for p in proxies if p["proto"] == proto]
    if limit:
        proxies = proxies[:limit]
    C.print(f"[cyan]Cek {len(proxies)} proxy (workers={workers}, timeout={timeout}s)...[/]")
    t0 = time.time()
    my_ip = fetcher.get_public_ip()
    C.print(f"[dim]IP kita: {my_ip}[/]")
    alive = fetcher.check_many(proxies, workers=workers, timeout=timeout)
    alive = fetcher.mark_transparent(alive, my_ip)
    # gabung dengan hasil lama (dedupe)
    old = _load(ALIVE)
    seen = {f"{p['proto']}://{p['host']}:{p['port']}" for p in alive}
    for p in old:
        k = f"{p['proto']}://{p['host']}:{p['port']}"
        if k not in seen:
            alive.append(p)
            seen.add(k)
    _save(ALIVE, alive)
    trans = sum(1 for p in alive if p.get("transparent"))
    C.print(f"[green]{len(alive)} proxy hidup ({round(time.time()-t0)}s) -> {ALIVE}[/] "
            f"[dim]({trans} transparan)[/]")


def cmd_update(workers, timeout, limit, ports=None, proto=None):
    cmd_fetch()
    cmd_check(workers, timeout, limit, ports, proto)


def cmd_list():
    raw = _load(RAW)
    alive = _load(ALIVE)
    C.print(f"[bold]Raw: {len(raw)}[/]  |  [bold green]Hidup: {len(alive)}[/]")
    if not alive:
        return
    t = Table(box=box.ROUNDED, title=f"Proxy hidup ({len(alive)})")
    t.add_column("Proxy", style="cyan")
    t.add_column("Proto")
    t.add_column("Egress", style="green")
    t.add_column("ms", justify="right")
    t.add_column("Sumber", style="dim")
    for p in sorted(alive, key=lambda x: x.get("ms", 9999))[:40]:
        t.add_row(p["raw"][:42], p["proto"], (p.get("egress") or "-")[:18],
                  str(p.get("ms", "-")), p.get("source", "-"))
    C.print(t)
    if len(alive) > 40:
        C.print(f"[dim]... dan {len(alive)-40} lagi[/]")
    # distribusi proto
    from collections import Counter
    C.print(f"proto: {dict(Counter(p['proto'] for p in alive))}")


def cmd_xai(limit=0, workers=30, timeout=15, target="https://accounts.x.ai/sign-up?redirect=grok-com"):
    """Filter proxy yang bisa mencapai target (default accounts.x.ai) -> file txt.

    Berguna untuk grok-suite (rotasi IP anti-flag). Hanya proxy non-transparan
    yang diuji.
    """
    import concurrent.futures as cf
    import urllib.error
    import urllib.request

    alive = _load(ALIVE)
    useful = [p for p in alive if not p.get("transparent")]
    http_ones = [p for p in useful if p["proto"] == "http"]
    if limit:
        http_ones = http_ones[:limit]
    if not http_ones:
        C.print("[yellow]Tidak ada proxy http berguna. Jalankan check dulu.[/]")
        return
    C.print(f"[cyan]Uji {len(http_ones)} proxy http -> {target}[/]")
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

    def reach(p):
        host, port = p["host"], p["port"]
        try:
            op = urllib.request.build_opener(urllib.request.ProxyHandler(
                {"http": f"http://{host}:{port}", "https": f"http://{host}:{port}"}))
            req = urllib.request.Request(target, headers={"User-Agent": ua})
            r = op.open(req, timeout=timeout)
            return {**p, "target_status": r.status}
        except urllib.error.HTTPError as e:
            return {**p, "target_status": e.code}
        except Exception:
            return None

    ok = []
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(reach, http_ones):
            if r and r.get("target_status") in (200, 403):
                ok.append(r)
                C.print(f"  OK {r['raw']:<42} status={r['target_status']} egress={r.get('egress','')[:24]}")

    out = DATA / "proxies_xai.txt"
    out.write_text("\n".join(p["raw"] for p in ok) + "\n")
    _save(DATA / "proxies_xai.json", ok)
    C.print(f"[green]{len(ok)}/{len(http_ones)} bisa capai target -> {out}[/]")


def cmd_export(fmt, no_transparent=False):
    alive = _load(ALIVE)
    if no_transparent:
        alive = [p for p in alive if not p.get("transparent")]
    if not alive:
        C.print("[yellow]Belum ada proxy hidup.[/]")
        return
    if fmt == "txt":
        out = DATA / "proxies.txt"
        out.write_text("\n".join(p["raw"] for p in alive) + "\n")
    elif fmt == "ipport":
        out = DATA / "proxies_ipport.txt"
        out.write_text("\n".join(f"{p['host']}:{p['port']}" for p in alive) + "\n")
    elif fmt == "json":
        out = DATA / "proxies.json"
        _save(out, alive)
    elif fmt == "csv":
        out = DATA / "proxies.csv"
        out.write_text("proto,host,port,user,password,egress,ms,source\n" +
                       "\n".join(f"{p['proto']},{p['host']},{p['port']},{p.get('user','')},"
                                 f"{p.get('password','')},{p.get('egress','')},{p.get('ms','')},{p.get('source','')}"
                                 for p in alive) + "\n")
    else:
        C.print(f"[red]format tak dikenal: {fmt}[/]"); return
    C.print(f"[green]{len(alive)} proxy -> {out}[/]")


def main():
    ap = argparse.ArgumentParser(prog="proxyscrape", description="ProxyScrape Suite")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("fetch")
    ck = sub.add_parser("check")
    ck.add_argument("--workers", type=int, default=200)
    ck.add_argument("--timeout", type=int, default=12)
    ck.add_argument("--limit", type=int, default=0)
    ck.add_argument("--ports", default=None, help="filter port, mis. '80,443,8080' (default: semua)")
    ck.add_argument("--proto", default=None, help="filter proto: http/socks4/socks5")
    up = sub.add_parser("update")
    up.add_argument("--workers", type=int, default=200)
    up.add_argument("--timeout", type=int, default=12)
    up.add_argument("--limit", type=int, default=0)
    up.add_argument("--ports", default=None)
    up.add_argument("--proto", default=None)
    sub.add_parser("list")
    xa = sub.add_parser("xai")
    xa.add_argument("--limit", type=int, default=0)
    xa.add_argument("--workers", type=int, default=30)
    xa.add_argument("--timeout", type=int, default=15)
    xa.add_argument("--target", default="https://accounts.x.ai/sign-up?redirect=grok-com")
    ex = sub.add_parser("export")
    ex.add_argument("--format", default="txt", choices=["txt", "ipport", "json", "csv"])
    ex.add_argument("--no-transparent", action="store_true", help="buang proxy transparan (egress = IP kita)")
    a = ap.parse_args()
    if a.cmd == "fetch":
        cmd_fetch()
    elif a.cmd == "check":
        cmd_check(a.workers, a.timeout, a.limit, a.ports, a.proto)
    elif a.cmd == "update":
        cmd_update(a.workers, a.timeout, a.limit, a.ports, a.proto)
    elif a.cmd == "list":
        cmd_list()
    elif a.cmd == "xai":
        cmd_xai(a.limit, a.workers, a.timeout, a.target)
    elif a.cmd == "export":
        cmd_export(a.format, a.no_transparent)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
