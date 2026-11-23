"""Hayes Watcher v1.1 - bao Telegram khi vi Arthur Hayes co giao dich lien quan ETH/BTC.

Chi bao khi trong giao dich co ETH hoac BTC (ban goc / ban "boc" tren Ethereum) di chuyen:
  - MUA / BAN ETH-BTC (swap voi coin khac)
  - SWAP giua ETH va BTC
  - NAP LEN SAN / RUT TU SAN (doi tac co nhan san giao dich / OTC)
  - CHUYEN RA / NHAN VAO (vi khac)
Bo qua: coin khac, token gia (loc theo dia chi hop dong, khong theo ten), tien rac sieu nho.
"""
import html
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

# ===================== CAU HINH =====================
WALLETS = [
    {"address": "0xA86e3D1C80a750A310b484FB9bDc470753A7506F", "name": "Arthur Hayes 2"},
]

# Nguong toi thieu de bao (duoi muc nay coi la tien rac, bo qua)
MIN_ETH = 0.1     # ETH (tinh ca WETH, stETH, wstETH, weETH)
MIN_BTC = 0.005   # BTC (tinh ca WBTC, cbBTC, tBTC)

# Token ETH/BTC that tren Ethereum (dia chi hop dong -> (ten, nhom))
TRACKED = {
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": ("WETH", "ETH"),
    "0xae7ab96520de3a18e5e111b5eaab095312d7fe84": ("stETH", "ETH"),
    "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0": ("wstETH", "ETH"),
    "0xcd5fe23c85820f7b72d0926fc9b05b43e359b7ee": ("weETH", "ETH"),
    "0x35fa164735182de50811e8e2e824cfb9b6118ac2": ("eETH", "ETH"),
    "0xbf5495efe5db9ce00f80364c8b423567e58d2110": ("ezETH", "ETH"),
    "0xa1290d69c65a6fe4df752f95823fae25cb99e5a7": ("rsETH", "ETH"),
    "0xae78736cd615f374d3085123a210448e74fc6393": ("rETH", "ETH"),
    "0xbe9895146f7af43049ca1c1ae358b0541ea49704": ("cbETH", "ETH"),
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": ("WBTC", "BTC"),
    "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf": ("cbBTC", "BTC"),
    "0x18084fba666a33d37592fa2633fd49a74dd93a88": ("tBTC", "BTC"),
}
# Stablecoin that (de hien "ban ETH lay USDC" cho dung, chong token gia ten USDC)
STABLES = {
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC",
    "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT",
    "0x6b175474e89094c44da98b954eedeac495271d0f": "DAI",
    "0x6c3ea9036406852006290770bedfcaba0e23a0e8": "PYUSD",
    "0x4c9edd5852cd905f086c759e8383e09bff1e68b3": "USDe",
}
# Tu khoa nhan dien san giao dich / ban OTC trong nhan cua Blockscout
EXCHANGE_WORDS = [
    "binance", "coinbase", "kraken", "okx", "okex", "bybit", "bitget", "kucoin", "gate.io",
    "gate ", "htx", "huobi", "bitfinex", "gemini", "crypto.com", "upbit", "bithumb", "mexc",
    "bitstamp", "deribit", "bitmex", "falconx", "flowdesk", "galaxy", "wintermute",
    "cumberland", "amber", "b2c2", "gsr", "jump", "anchorage", "copper", "fireblocks",
    "exchange", "hot wallet", "deposit",
]

VERSION = "v1.1"
CHAIN_ID = "1"  # Ethereum
EXPLORER_TX = "https://etherscan.io/tx/"
EXPLORER_ADDR = "https://etherscan.io/address/"
STATE_FILE = "state.json"
KST = timezone(timedelta(hours=9))
# ====================================================

API_KEY = os.environ.get("BLOCKSCOUT_API_KEY", "").strip()
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

API_BASES = [
    f"https://api.blockscout.com/{CHAIN_ID}/api",
    "https://api.blockscout.com/v2/api",
    "https://eth.blockscout.com/api",  # du phong (khong can key)
]
V2_BASE = "https://eth.blockscout.com/api/v2"


def http_get_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "hayes-watcher/1.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def api_raw(params):
    errors = []
    for base in API_BASES:
        p = dict(params)
        if "api.blockscout.com" in base:
            if not API_KEY:
                continue
            p["apikey"] = API_KEY
        if "/v2/" in base:
            p["chainid"] = CHAIN_ID
        url = base + "?" + urllib.parse.urlencode(p)
        try:
            data = http_get_json(url)
        except Exception as e:
            errors.append(f"{base.split('/')[2]}: {e}")
            continue
        result = data.get("result")
        if isinstance(result, list):
            return result
        if result not in (None, "") and not (isinstance(result, str) and "error" in result.lower()):
            return result
        errors.append(f"{base.split('/')[2]}: {data.get('message')} {str(result)[:100]}")
    raise RuntimeError("API loi: " + " | ".join(errors))


def api(params):
    result = api_raw(params)
    if isinstance(result, list):
        return result
    if isinstance(result, str) and "no " in result.lower():
        return []
    raise RuntimeError(f"API tra ve khong phai danh sach: {result}")


def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    body = urllib.parse.urlencode({
        "chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(url, data=body)
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.loads(r.read().decode())
    if not res.get("ok"):
        raise RuntimeError(f"Telegram loi: {res}")


def head_block():
    for params in ({"module": "block", "action": "eth_block_number"},
                   {"module": "proxy", "action": "eth_blockNumber"}):
        try:
            res = api_raw(params)
            return int(res, 16) if isinstance(res, str) and res.startswith("0x") else int(res)
        except Exception as e:
            print("  khong lay duoc block moi nhat:", e)
    return None


def eth_balance(addr):
    try:
        return int(api_raw({"module": "account", "action": "balance", "address": addr})) / 1e18
    except Exception as e:
        print("  khong lay duoc so du:", e)
        return None


def holdings_text(addr, prices):
    """Tong so du ETH goc + cac token ETH/BTC that (bo qua token = 0)."""
    lines, total = [], 0.0
    bal = eth_balance(addr)
    items = [("ETH", "ETH", bal)]
    for ca, (sym, grp) in TRACKED.items():
        try:
            raw = api_raw({"module": "account", "action": "tokenbalance",
                           "contractaddress": ca, "address": addr})
            dec = 8 if grp == "BTC" else 18
            items.append((sym, grp, int(raw) / 10 ** dec))
        except Exception as e:
            print("  khong lay duoc so du", sym, e)
    for sym, grp, amt in items:
        if amt is None or amt <= 0:
            continue
        s = f"• {fmt_num(amt)} {sym}"
        if grp in prices:
            usd = amt * prices[grp]
            total += usd
            s += f" (~{fmt_usd(usd)})"
        lines.append(s)
    head = f"💰 Đang giữ (ETH/BTC): ~{fmt_usd(total)}" if total else "💰 Đang giữ (ETH/BTC):"
    return head + "\n" + ("\n".join(lines) or "• (không lấy được số dư)")


def get_prices():
    """Gia ETH, BTC (USD) tu CoinGecko. Loi thi tra ve {} (tin van gui, chi thieu $)."""
    try:
        d = http_get_json("https://api.coingecko.com/api/v3/simple/price"
                          "?ids=ethereum,bitcoin&vs_currencies=usd")
        return {"ETH": float(d["ethereum"]["usd"]), "BTC": float(d["bitcoin"]["usd"])}
    except Exception as e:
        print("  khong lay duoc gia:", e)
        return {}


def label_of(addr, cache):
    """Ten/nhan cua dia chi doi tac (Blockscout). Ghi nho trong state de khoi hoi lai."""
    addr = addr.lower()
    if addr in cache:
        return cache[addr]
    name = ""
    try:
        d = http_get_json(f"{V2_BASE}/addresses/{addr}")
        parts = []
        if d.get("name"):
            parts.append(d["name"])
        for t in ((d.get("metadata") or {}).get("tags") or []):
            if t.get("name"):
                parts.append(t["name"])
        for key in ("public_tags", "private_tags"):
            for t in d.get(key) or []:
                if t.get("display_name"):
                    parts.append(t["display_name"])
        seen, uniq = set(), []
        for p in parts:
            if p.lower() not in seen:
                seen.add(p.lower())
                uniq.append(p)
        name = " · ".join(uniq[:3])
    except Exception as e:
        print("  khong tra duoc nhan", addr, e)
    cache[addr] = name
    return name


def is_exchange(label):
    low = (label or "").lower()
    return any(w in low for w in EXCHANGE_WORDS)


def fmt_num(x):
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    if abs(x) >= 1:
        return f"{x:,.2f}"
    return f"{x:.4f}".rstrip("0").rstrip(".")


def fmt_usd(x):
    if x >= 1_000_000:
        return f"${x / 1_000_000:,.2f}M"
    if x >= 1000:
        return f"${x / 1000:,.1f}K"
    return f"${x:,.0f}"


def short(addr):
    return f"{addr[:6]}…{addr[-4:]}"


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ---------------- Phan tich giao dich ----------------
def analyze(wallet, txs, toks, ints):
    """Gom theo ma giao dich. Tra ve danh sach su kien ETH/BTC (da loc rac)."""
    wallet = wallet.lower()
    groups = {}

    def g(t):
        h = (t.get("hash") or t.get("transactionHash") or "").lower()
        if not h:
            return None
        return groups.setdefault(h, {"hash": h, "block": int(t.get("blockNumber") or 0),
                                     "time": int(t.get("timeStamp") or 0),
                                     "moves": [], "parties": {}, "fail": False})

    def add(e, asset, group, amount, direction, party):
        # direction: +1 vao vi, -1 ra khoi vi
        e["moves"].append({"asset": asset, "group": group, "amt": amount, "dir": direction})
        if party:
            e["parties"][party.lower()] = e["parties"].get(party.lower(), 0) + 1

    for t in txs:
        e = g(t)
        if e is None:
            continue
        if str(t.get("isError", "0")) != "0" or str(t.get("txreceipt_status", "1")) == "0":
            e["fail"] = True
            continue
        v = int(t.get("value") or 0) / 1e18
        if v <= 0:
            continue
        fr, to = t.get("from", "").lower(), t.get("to", "").lower()
        if fr == wallet:
            add(e, "ETH", "ETH", v, -1, to)
        elif to == wallet:
            add(e, "ETH", "ETH", v, +1, fr)

    for t in ints:
        e = g(t)
        if e is None or str(t.get("isError", "0")) != "0":
            continue
        v = int(t.get("value") or 0) / 1e18
        if v <= 0:
            continue
        fr, to = t.get("from", "").lower(), t.get("to", "").lower()
        if to == wallet and fr != wallet:
            add(e, "ETH", "ETH", v, +1, fr)
        elif fr == wallet and to != wallet:
            add(e, "ETH", "ETH", v, -1, to)

    for t in toks:
        e = g(t)
        if e is None:
            continue
        ca = (t.get("contractAddress") or "").lower()
        fr, to = t.get("from", "").lower(), t.get("to", "").lower()
        if fr == to:
            continue
        direction = -1 if fr == wallet else (+1 if to == wallet else 0)
        if not direction:
            continue
        dec = int(t.get("tokenDecimal") or 18)
        amt = int(t.get("value") or 0) / 10 ** dec
        party = to if direction < 0 else fr
        if ca in TRACKED:
            sym, grp = TRACKED[ca]
            add(e, sym, grp, amt, direction, party)
        elif ca in STABLES:
            add(e, STABLES[ca], "STABLE", amt, direction, party)
        # token khac: bo qua hoan toan (ke ca token gia ten ETH/BTC/USDC)

    events = []
    for e in sorted(groups.values(), key=lambda x: (x["block"], x["hash"])):
        if e["fail"]:
            continue
        # Cong don theo tung tai san (vao - ra)
        net = {}
        for m in e["moves"]:
            k = (m["asset"], m["group"])
            net[k] = net.get(k, 0.0) + m["amt"] * m["dir"]
        eth_moved = sum(abs(v) for (a, gr), v in net.items() if gr == "ETH")
        btc_moved = sum(abs(v) for (a, gr), v in net.items() if gr == "BTC")
        if eth_moved < MIN_ETH and btc_moved < MIN_BTC:
            continue  # khong co ETH/BTC dang ke -> khong bao
        outs = [(a, gr, -v) for (a, gr), v in net.items() if v < -1e-12]
        ins = [(a, gr, v) for (a, gr), v in net.items() if v > 1e-12]
        events.append({"hash": e["hash"], "block": e["block"], "time": e["time"],
                       "outs": outs, "ins": ins, "parties": e["parties"]})
    return events


def classify(ev, labels):
    """Tra ve (tieu de, doi tac chinh, nhan doi tac)."""
    outs, ins = ev["outs"], ev["ins"]
    out_g = {gr for _, gr, _ in outs}
    in_g = {gr for _, gr, _ in ins}
    party = max(ev["parties"], key=ev["parties"].get) if ev["parties"] else ""
    lab = labels.get(party, "") if party else ""
    crypto = {"ETH", "BTC"}

    if outs and ins:
        # Doi ETH <-> WETH (cung nhom) coi la boc/mo boc
        if out_g == in_g and len(out_g) == 1:
            return "🔁 Đổi qua lại (wrap/stake)", party, lab
        bought = sorted(in_g & crypto)
        sold = sorted(out_g & crypto)
        if bought and sold:
            return f"🔄 SWAP {'/'.join(sold)} → {'/'.join(bought)}", party, lab
        if bought:
            return f"🟢 MUA {'/'.join(bought)}", party, lab
        return f"🔴 BÁN {'/'.join(sold)}", party, lab
    grp = "/".join(sorted((out_g | in_g) & crypto)) or "ETH"
    if outs:
        if is_exchange(lab):
            return f"🏦 NẠP {grp} LÊN SÀN/OTC", party, lab
        return f"📤 CHUYỂN {grp} RA", party, lab
    if is_exchange(lab):
        return f"🏦 RÚT {grp} TỪ SÀN/OTC", party, lab
    return f"📥 NHẬN {grp} VÀO", party, lab


def leg_text(items, prices):
    parts = []
    for asset, grp, amt in items:
        s = f"{fmt_num(amt)} {html.escape(asset)}"
        if grp in prices:
            s += f" (~{fmt_usd(amt * prices[grp])})"
        elif grp == "STABLE":
            s += f" (~{fmt_usd(amt)})"
        parts.append(s)
    return ", ".join(parts) or "—"


def build_message(name, ev, title, party, lab, prices):
    dt = datetime.fromtimestamp(ev["time"], KST) if ev["time"] else datetime.now(KST)
    lines = [f"<b>{title}</b> · {html.escape(name)}"]
    if ev["outs"]:
        lines.append("➖ Ra khỏi ví: " + leg_text(ev["outs"], prices))
    if ev["ins"]:
        lines.append("➕ Vào ví: " + leg_text(ev["ins"], prices))
    if party:
        who = html.escape(lab) if lab else "ví/hợp đồng chưa có nhãn"
        lines.append(f'🤝 Đối tác: {who} (<a href="{EXPLORER_ADDR}{party}">{short(party)}</a>)')
    lines.append(f"⏰ {dt.strftime('%d/%m %H:%M')} (giờ Hàn)")
    lines.append(f'🔗 <a href="{EXPLORER_TX}{ev["hash"]}">Xem giao dịch</a>')
    return "\n".join(lines)


def fetch(wallet, start_block):
    rng = {"address": wallet, "startblock": start_block, "endblock": 999999999,
           "sort": "asc", "page": 1, "offset": 1000}
    txs = api(dict(rng, module="account", action="txlist"))
    toks = api(dict(rng, module="account", action="tokentx"))
    try:
        ints = api(dict(rng, module="account", action="txlistinternal"))
    except Exception as e:
        print("  khong lay duoc giao dich noi bo:", e)
        ints = []
    return txs, toks, ints


def check_wallet(cfg, ws, labels, prices):
    wallet = cfg["address"].lower()
    name = cfg["name"]
    if not ws.get("started"):
        send_telegram(
            f"✅ <b>Đã bật theo dõi: {html.escape(name)}</b>\n"
            f'Ví <a href="{EXPLORER_ADDR}{wallet}">{short(wallet)}</a> (Ethereum)\n'
            f"{holdings_text(wallet, prices)}\n"
            f"Chỉ báo giao dịch ETH/BTC: mua bán, swap, nạp rút sàn "
            f"(từ {MIN_ETH} ETH / {MIN_BTC} BTC trở lên)."
        )
        ws["started"] = True
        ws["version"] = VERSION
    elif ws.get("version") != VERSION:
        # Bao 1 lan khi cap nhat code: so du day du (ca token ETH/BTC)
        send_telegram(
            f"🔧 <b>Bot đã cập nhật {VERSION}</b> · {html.escape(name)}\n"
            f"Đã thêm theo dõi eETH (ether.fi) và các ETH stake khác.\n"
            f"{holdings_text(wallet, prices)}"
        )
        ws["version"] = VERSION

    start = ws["last_block"] + 1
    txs, toks, ints = fetch(wallet, start)
    all_blocks = [int(t.get("blockNumber") or 0) for t in txs + toks + ints]
    events = [e for e in analyze(wallet, txs, toks, ints) if e["block"] >= start]
    print(f"[{name}] {len(txs)}/{len(toks)}/{len(ints)} ban ghi, {len(events)} su kien ETH/BTC")

    for ev in events:
        for p in ev["parties"]:
            label_of(p, labels)
        title, party, lab = classify(ev, labels)
        send_telegram(build_message(name, ev, title, party, lab, prices))
        print("  Da bao:", ev["hash"], title)

    if all_blocks:
        ws["last_block"] = max(ws["last_block"], max(all_blocks))


def main():
    for key, val in [("TELEGRAM_BOT_TOKEN", BOT_TOKEN), ("TELEGRAM_CHAT_ID", CHAT_ID)]:
        if not val:
            print(f"THIEU SECRET: {key}")
            return
    if not API_KEY:
        print("Khong co BLOCKSCOUT_API_KEY -> dung API cong khai eth.blockscout.com")

    state = load_state()
    state.setdefault("wallets", {})
    state.setdefault("labels", {})
    before = json.dumps(state, sort_keys=True)
    prices = get_prices()

    try:
        for cfg in WALLETS:
            addr = cfg["address"].lower()
            if addr not in state["wallets"]:
                head = head_block()
                if head is None:
                    print(f"[{cfg['name']}] chua lay duoc block hien tai, thu lai lan sau")
                    continue
                # Vi moi: bat dau tu bay gio, bo qua lich su cu
                state["wallets"][addr] = {"last_block": head, "started": False}
            try:
                check_wallet(cfg, state["wallets"][addr], state["labels"], prices)
            except Exception as e:
                print(f"LOI [{cfg['name']}]:", e)
    finally:
        if json.dumps(state, sort_keys=True) != before:
            save_state(state)
            print("Da luu state.json")


if __name__ == "__main__":
    main()
    sys.exit(0)
