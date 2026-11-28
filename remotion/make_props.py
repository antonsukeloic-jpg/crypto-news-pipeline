import subprocess
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
    if s.get('real'):
        sc['real'] = True
        if s.get('credit'): sc['credit'] = s['credit']
        try:
            wh = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0',
                                 os.path.join(pub, sc.get('image', ''))], capture_output=True, text=True, timeout=10).stdout.strip().split(',')
            sc['aspect'] = round(int(wh[0]) / int(wh[1]), 3)
        except Exception:
            pass
    if s.get('vo_segment'): sc['vo_segment'] = s['vo_segment']
    scenes.append(sc)
# where the person / main object is in each real photo (covers + carousel crop around it); optional, fail-safe
_fp = '/opt/focus/bin/python'
_imgs = [os.path.join(pub, sc['image']) for sc in scenes if sc.get('real') and sc.get('image')]
if _imgs and os.path.exists(_fp):
    try:
        _f = json.loads(subprocess.run([_fp, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'focus.py')] + _imgs,
                                       capture_output=True, text=True, timeout=60).stdout or '{}')
        for sc in scenes:
            if sc.get('image') and os.path.join(pub, sc['image']) in _f:
                sc['focus'] = _f[os.path.join(pub, sc['image'])]
    except Exception:
        pass
out_obj = {'scenes': scenes, 'voice': voice_base, 'fps': 30}
if job.get('ticker'): out_obj['ticker'] = job['ticker']
if job.get('captions'): out_obj['captions'] = job['captions']
if job.get('cta'): out_obj['cta'] = job['cta']   # ad end card (vikops)
# per-video music bed (5HU): copy it next to the voice; if generation failed the renderer uses its fallback track
if job.get('music') and os.path.exists(os.path.join(root, job['music'])):
    mb = os.path.basename(job['music'])
    shutil.copy(os.path.join(root, job['music']), os.path.join(pub, mb))
    out_obj['music'] = mb
if job.get('bpm'): out_obj['bpm'] = job['bpm']
channel = job.get('channel') or 'crypto'
# 5HU photo carousel copy + designer accounts (FiveHuCarousel)
if job.get('carousel'): out_obj['carousel'] = job['carousel']
if job.get('creators'): out_obj['creators'] = job['creators']
if job.get('episode'): out_obj['episode'] = int(job['episode'])          # 5HU series number (Who's Next Nº…)
if job.get('end_question'): out_obj['end_question'] = str(job['end_question'])[:60]   # two-option question in the outro
if job.get('silent'): out_obj['silent'] = True   # A/B (2026-11-28): no AI voice - words on screen + music only
if job.get('send_cta'): out_obj['send_cta'] = True   # A/B (2026-11-27): outro asks people to send it to a friend (DM sends = top IG reach signal)
out_obj['channel'] = channel
# 5HU: fixed brand sign-off ("Follow Šū, we find them first.") played after the voice; render_vps.sh copies music/*.mp3 into public/music
so = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'music', '5hu_signoff.mp3')
if channel == '5hu' and job.get('signoff') and os.path.exists(so):
    out_obj['signoff'] = 'music/5hu_signoff.mp3'
    try:
        out_obj['signoffSec'] = round(float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', so],
                                                          capture_output=True, text=True, timeout=10).stdout.strip()), 2)
    except Exception:
        out_obj['signoffSec'] = 2.6
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
