# ProxyScrape Suite

Agregator + validator **proxy publik gratis**. Ambil dari **21 sumber** secara
paralel → dedupe → cek hidup → ekspor ke berbagai format.

## Fitur

- **21 sumber**: ProxyScrape v2/v4, TheSpeedX, monosans, proxifly, geonode,
  openproxylist, clarketm, ShiftyTR, roosterkid, hookzof, jetkai.
- **Fetch paralel** — 57.000+ proxy unik dalam ~1 detik.
- **Validasi nyata** — TCP connect + HTTP GET ke endpoint echo-IP (bukan cuma ping).
- **Dukungan HTTP + SOCKS4 + SOCKS5** (SOCKS via PySocks).
- **Ekspor** txt / ipport / json / csv.

## Instalasi

```bash
python3 -m venv .venv
.venv/bin/pip install rich requests pysocks
```

## Command

```bash
./run.sh fetch                              # ambil dari semua sumber -> data/raw.json
./run.sh check                              # cek semua -> data/alive.json
./run.sh check --ports 80,443,8080          # cek hanya port tertentu (lebih cepat)
./run.sh check --proto http --limit 2000    # filter proto + batasi jumlah
./run.sh update                             # fetch + check (satu perintah)
./run.sh list                               # ringkasan + tabel proxy hidup
./run.sh export --format txt                # ekspor (txt|ipport|json|csv)
```

Parameter `check`/`update`: `--workers` (default 200), `--timeout` (12s),
`--limit`, `--ports`, `--proto`.

## Contoh alur

```bash
# 1. ambil semua sumber
./run.sh fetch
#   -> 57408 proxy unik

# 2. validasi (hanya port yang bisa dijangkau, lebih cepat)
./run.sh check --ports 80,443,8080 --workers 300
#   -> 384 hidup dari 4017 dicek (91s); 183 transparan dibuang -> 201 berguna

# 3. ekspor
./run.sh export --format txt
```

## Format data

`data/raw.json` — semua proxy mentah:
```json
[{"proto":"http","host":"1.2.3.4","port":"8080","user":"","password":"","raw":"http://1.2.3.4:8080","source":"proxyscrape_v4_http"}]
```

`data/alive.json` — proxy yang terbukti hidup, plus `egress` (IP keluar asli),
`ms` (latensi), `tcp_ms`, `transparent` (true bila egress == IP kita).

Contoh hasil nyata: **57408 raw → 4017 (port 80/443/8080) → 384 hidup → 201 berguna**
(183 transparan dibuang). 17 di antaranya terbukti bisa mencapai `accounts.x.ai`.

## ⚠️ Catatan penting

- **Proxy transparan**: sebagian proxy mengembalikan `egress` = IP Anda sendiri
  (artinya tidak benar-benar menyembunyikan IP). Cek field `egress` — kalau
  sama dengan IP publik Anda, proxy itu transparan (kurang berguna untuk
  anonimitas).
- **Rate-limit / firewall**: lingkungan dengan egress terbatas (mis. hanya
  port 80/443/8080) hanya bisa memvalidasi proxy di port tersebut. Gunakan
  `--ports` untuk menyesuaikan.
- **Umur proxy gratis pendek** — jalankan `update` berkala (cron) untuk
  menyegarkan daftar.
- Proxy publik gratis **tidak untuk data sensitif** (bisa di-log pihak lain).

## Struktur

```
main.py              # CLI
src/sources.py       # registry 21 sumber + parser
src/fetcher.py       # fetch paralel + checker
data/raw.json        # hasil fetch
data/alive.json      # proxy hidup
```

## Integrasi

`data/proxies.txt` (hasil `export`) bisa langsung dipakai suite lain, mis.
`grok-suite/batch.py --proxy-file data/proxies.txt`.

## 🔗 Integrasi dengan grok-suite

Command `xai` memfilter proxy yang benar-benar bisa mencapai `accounts.x.ai`
(berguna untuk rotasi IP di grok-suite):

```bash
./run.sh xai                    # uji semua proxy berguna -> data/proxies_xai.txt
./run.sh xai --limit 100        # batasi jumlah
./run.sh xai --target https://... # target lain
```

grok-suite memakainya otomatis lewat `./run.sh refresh-proxies`.

## 🔒 scan-secrets.sh — cek sebelum publish

Utility untuk memastikan **tidak ada data sensitif** yang ikut ter-upload
(kredensial, API key, proxy ber-auth, endpoint pribadi, file akun).

```bash
./scan-secrets.sh            # scan repo ini
./scan-secrets.sh /path/repo # scan repo lain
./test-scan-secrets.sh       # uji detektornya (8 kasus)
```

Cek **dua lapis**:
1. **working tree** — hanya file yang ter-track
2. **git history** — SEMUA commit (file yang sudah dihapus pun ketahuan)

Keluar `exit 1` kalau ada temuan CRITICAL → jangan publish.

Menandai baris yang sengaja memuat pola palsu (fixture/contoh):

```python
FAKE = "sk-..."  # scan-secrets:allow
```
