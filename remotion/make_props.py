import sys, json, os, shutil, urllib.request

def _get(url, timeout=5):
    req = urllib.request.Request(url, headers={'User-Agent': 'CryptoNewsFactory/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def fetch_btc():
    # ordered sources; first sane answer wins -> (price:int, change:float|None)
    def binance():
        d = _get('https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT')
        return float(d['lastPrice']), float(d['priceChangePercent'])
    def coincap():
        d = _get('https://api.coincap.io/v2/assets/bitcoin')['data']
        return float(d['priceUsd']), float(d['changePercent24Hr'])
    def coingecko():
        d = _get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true')['bitcoin']
        return float(d['usd']), float(d['usd_24h_change'])
    def kraken():
        res = _get('https://api.kraken.com/0/public/Ticker?pair=XBTUSD')['result']
        k = list(res.keys())[0]; t = res[k]
        last = float(t['c'][0]); op = float(t['o'])
        return last, ((last - op) / op * 100.0 if op else None)
    def coinbase():
        d = _get('https://api.coinbase.com/v2/prices/BTC-USD/spot')['data']
        return float(d['amount']), None
    for fn in (binance, coincap, coingecko, kraken, coinbase):
        try:
            price, change = fn()
            if price and 1000 < price < 10000000:
                return int(round(price)), (round(change, 1) if change is not None else None)
        except Exception:
            pass
    return None, None

job_path, root, pub, out = sys.argv[1:5]
job = json.load(open(job_path))
os.makedirs(pub, exist_ok=True)
voice_base = os.path.basename(job['voice'])
shutil.copy(os.path.join(root, job['voice']), os.path.join(pub, voice_base))
scenes = []
for s in job['scenes']:
    sc = {'duration': s['duration'], 'on_screen_text': s.get('on_screen_text', '')}
    if s.get('video'):
        b = os.path.basename(s['video']); shutil.copy(os.path.join(root, s['video']), os.path.join(pub, b)); sc['video'] = b
    else:
        b = os.path.basename(s['image']); shutil.copy(os.path.join(root, s['image']), os.path.join(pub, b)); sc['image'] = b
    if s.get('center'): sc['center'] = s['center']
    if s.get('vo_segment'): sc['vo_segment'] = s['vo_segment']
    scenes.append(sc)
out_obj = {'scenes': scenes, 'voice': voice_base, 'fps': 30}
if job.get('ticker'): out_obj['ticker'] = job['ticker']
if job.get('captions'): out_obj['captions'] = job['captions']
channel = job.get('channel') or 'crypto'
out_obj['channel'] = channel
bp = bc = None
if channel == 'crypto':
    # BTC live at render time (multi-source); fall back to job seed if all fail
    bp, bc = fetch_btc()
    if bp is None:
        bp = job.get('btc_price'); bc = job.get('btc_change_24h')
    if bp is not None: out_obj['btc_price'] = bp
    if bc is not None: out_obj['btc_change_24h'] = bc
# other channels (e.g. "lt"): no BTC fetch, no BTC overlay
json.dump(out_obj, open(out, 'w'))
print('props ok channel=%s scenes=%d btc=%s change=%s' % (channel, len(scenes), bp, bc))
