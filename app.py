# ============================================================
# TRADING APP - STREAMLIT CLOUD - HANDY OPTIMIERT
# LTC KSM XRP XLM SHX - LONG / SHORT + ABC + Fibo + Score
# ============================================================
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Trading App", layout="wide", initial_sidebar_state="collapsed")

# ===== HANDY STYLE - Grosse Buttons, grosse Schrift =====
st.markdown("""
<style>
.stApp { background-color: #0d1117; color: white; }
h1 { font-size: 26px !important; text-align: center; }
h2, h3 { font-size: 19px !important; }
div[data-testid="stMetric"] { background-color: #161b22; border: 1px solid #21262d; border-radius: 16px; padding: 12px; }
div[data-testid="stMetricLabel"] { color: #aaa !important; font-size: 13px !important; }
div[data-testid="stMetricValue"] { color: white !important; font-size: 22px !important; }
.stButton > button { width: 100%; padding: 16px; font-size: 17px !important; font-weight: 800; border-radius: 12px; background: #1f6feb; color: white; border: none; }
.stSelectbox, .stRadio, .stNumberInput { font-size: 16px; }
[data-testid="stSidebar"] { background-color: #161b22; }
</style>
""", unsafe_allow_html=True)

def hole_kerzen(symbol, interval, limit=300):
    try:
        bi = '15' if interval=='15m' else '60' if interval=='1h' else 'D'
        url = f'https://api.bybit.com/v5/market/kline?category=spot&symbol={symbol}&interval={bi}&limit={limit}'
        r = requests.get(url, timeout=10)
        j = r.json()
        if j.get('result') and j['result'].get('list'):
            data = j['result']['list'][::-1]
            df = pd.DataFrame(data, columns=['time','open','high','low','close','vol','turnover'])
            df = df[['time','open','high','low','close','vol']].astype(float)
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            if len(df) >= 50: return df
    except: pass
    try:
        url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}'
        r = requests.get(url, timeout=10)
        if r.status_code==200:
            d = r.json()
            df = pd.DataFrame(d, columns=['time','open','high','low','close','vol','ct','qa','nt','tb','tq','ig'])
            df = df[['time','open','high','low','close','vol']].astype(float)
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            if len(df)>=50: return df
    except: pass
    return None

def berechne_rsi(closes, periode=14):
    if len(closes) < periode+2: return 50.0
    gains, losses = 0, 0
    for i in range(1, periode+1):
        d = closes[i]-closes[i-1]
        if d>=0: gains+=d
        else: losses+=-d
    ag=gains/periode; al=losses/periode
    for i in range(periode+1, len(closes)):
        d=closes[i]-closes[i-1]
        g=d if d>0 else 0; l=-d if d<0 else 0
        ag=(ag*(periode-1)+g)/periode; al=(al*(periode-1)+l)/periode
    if al==0: return 100.0
    if ag==0: return 0.0
    rs=ag/al
    return 100-(100/(1+rs))

def berechne_ema(data, periode):
    k=2/(periode+1)
    ema=sum(data[:periode])/periode
    for i in range(periode, len(data)):
        ema=data[i]*k+ema*(1-k)
    return ema

def berechne_macd(closes):
    if len(closes)<30: return 0
    return berechne_ema(closes,12)-berechne_ema(closes,26)

def finde_swing(df, lookback=100):
    data=df.tail(lookback).copy()
    idx_high=data['high'].idxmax(); idx_low=data['low'].idxmin()
    sh=float(data.loc[idx_high,'high']); sl=float(data.loc[idx_low,'low'])
    is_up=idx_high>idx_low
    if is_up: sl=float(data.loc[:idx_high,'low'].min())
    else: sh=float(data.loc[:idx_low,'high'].max())
    return sh, sl, is_up

def berechne_fibos(sh, sl, is_up):
    diff=sh-sl
    if is_up:
        return {'0':sh,'0.236':sh-diff*0.236,'0.382':sh-diff*0.382,'0.5':sh-diff*0.5,'0.618':sh-diff*0.618,'0.786':sh-diff*0.786,'1':sl,'-0.272':sh+diff*0.272,'-0.618':sh+diff*0.618}, diff
    else:
        return {'0':sl,'0.236':sl+diff*0.236,'0.382':sl+diff*0.382,'0.5':sl+diff*0.5,'0.618':sl+diff*0.618,'0.786':sl+diff*0.786,'1':sh,'-0.272':sl-diff*0.272,'-0.618':sl-diff*0.618}, diff

def finde_pivots(df, links=3):
    pivots=[]; closes=df.reset_index(drop=True)
    for i in range(links, len(closes)-links):
        is_high=True; is_low=True
        for j in range(1, links+1):
            if closes.loc[i,'high'] < closes.loc[i-j,'high'] or closes.loc[i,'high'] < closes.loc[i+j,'high']: is_high=False
            if closes.loc[i,'low'] > closes.loc[i-j,'low'] or closes.loc[i,'low'] > closes.loc[i+j,'low']: is_low=False
        if is_high: pivots.append({'idx':i,'preis':float(closes.loc[i,'high']),'typ':'HOCH'})
        if is_low: pivots.append({'idx':i,'preis':float(closes.loc[i,'low']),'typ':'TIEF'})
    pivots=sorted(pivots, key=lambda x: x['idx'])
    gef=[]
    for p in pivots:
        if not gef or gef[-1]['typ']!=p['typ']: gef.append(p)
        else:
            last=gef[-1]
            if p['typ']=='HOCH' and p['preis']>last['preis']: gef[-1]=p
            if p['typ']=='TIEF' and p['preis']<last['preis']: gef[-1]=p
    return gef

def berechne_abc(df):
    if df is None or len(df)<50: return None
    pivots=finde_pivots(df)
    if len(pivots)<4: return None
    p=pivots[-4:]; preis=float(df['close'].iloc[-1])
    start,a,b=p[0],p[1],p[2]
    ist_ab = (start['typ']=='HOCH' and a['typ']=='TIEF' and b['typ']=='HOCH')
    ist_auf = (start['typ']=='TIEF' and a['typ']=='HOCH' and b['typ']=='TIEF')
    if not ist_ab and not ist_auf: return None
    if ist_ab:
        lenA=start['preis']-a['preis']; retrace=(b['preis']-a['preis'])/lenA if lenA else 0
        z100=b['preis']-lenA; z1618=b['preis']-lenA*1.618; z0786=b['preis']-lenA*0.786
        if preis>b['preis']: welle='ABC ABGESCHLOSSEN ✅'; fazit='Preis über B-Hoch = Korrektur vorbei!'; bonus=12
        elif abs(preis-z100)/z100<0.02 or abs(preis-z1618)/z1618<0.02: welle='WELLE C - ENDE NAHE 🎯'; fazit=f'Preis fast am C-Ziel! C=1.0 bei {z100:.4f} $'; bonus=10
        elif preis<b['preis'] and preis>a['preis']: welle='WELLE B LÄUFT ⏳'; fazit=f'B holt {retrace*100:.0f}% von A zurück. Danach kommt C runter. Jetzt NICHT kaufen!'; bonus=-8
        elif preis<a['preis']: welle='WELLE C LÄUFT 🔴'; fazit=f'Wir sind in C. Ziel 1.0: {z100:.4f} $'; bonus=-5
        else: welle='ABC UNKLAR'; fazit='ABC erkennbar.'; bonus=0
        return {'typ':'ABWÄRTS','start':start,'a':a,'b':b,'lenA':lenA,'retrace':retrace,'z100':z100,'z1618':z1618,'z0786':z0786,'welle':welle,'fazit':fazit,'bonus':bonus,'preis':preis}
    if ist_auf:
        lenA=a['preis']-start['preis']; retrace=(a['preis']-b['preis'])/lenA if lenA else 0
        z100=b['preis']+lenA; z1618=b['preis']+lenA*1.618; z0786=b['preis']+lenA*0.786
        if preis<b['preis']: welle='ABC ABGESCHLOSSEN ✅'; fazit='Preis unter B-Tief = ABC fertig.'; bonus=-12
        elif abs(preis-z100)/z100<0.02 or abs(preis-z1618)/z1618<0.02: welle='WELLE C - ENDE NAHE 🎯'; fazit='Preis fast am C-Ziel oben! Top nahe!'; bonus=-10
        elif preis>b['preis'] and preis<a['preis']: welle='WELLE B LÄUFT ⏳'; fazit='In B-Korrektur.'; bonus=8
        elif preis>a['preis']: welle='WELLE C LÄUFT 🟢'; fazit=f'Wir sind in C hoch. Ziel: {z100:.4f} $'; bonus=5
        else: welle='ABC UNKLAR'; fazit='ABC erkennbar.'; bonus=0
        return {'typ':'AUFWÄRTS','start':start,'a':a,'b':b,'lenA':lenA,'retrace':retrace,'z100':z100,'z1618':z1618,'z0786':z0786,'welle':welle,'fazit':fazit,'bonus':bonus,'preis':preis}
    return None

def berechne_divergenz(closes):
    if len(closes)<30: return 'KEINE'
    letzte30=closes[-30:]; erste, zweite=letzte30[:15], letzte30[15:]
    tief1, tief2=min(erste), min(zweite); hoch1, hoch2=max(erste), max(zweite)
    rsi1=berechne_rsi(closes[:-15],14); rsi2=berechne_rsi(closes,14)
    if tief2<tief1 and rsi2>rsi1: return 'BULLISCHE DIVERGENZ 🟢'
    if hoch2>hoch1 and rsi2<rsi1: return 'BÄRISCHE DIVERGENZ 🔴'
    return 'KEINE'

def berechne_sweep(df):
    if df is None or len(df)<30: return 'KEIN SWEEP'
    last=df.iloc[-1]; lows=df['low'].iloc[-21:-1].min(); highs=df['high'].iloc[-21:-1].max()
    if last['low']<lows and last['close']>lows and last['close']>last['open']:
        return f'BULLISH SWEEP 🟢🟢 - Unter {lows:.4f} $ gedippt und zurück!'
    if last['high']>highs and last['close']<highs and last['close']<last['open']:
        return f'BEARISH SWEEP 🔴🔴 - Über {highs:.4f} $ gedippt und zurück!'
    return 'KEIN SWEEP'

def hole_btc():
    df=hole_kerzen('BTCUSDT','1h',200)
    if df is None: return 'UNBEKANNT',0,50
    closes=df['close'].tolist(); preis=closes[-1]; rsi=berechne_rsi(closes,14); ema50=berechne_ema(closes,50)
    if preis>ema50 and rsi>50: sig='BULLISCH'
    elif preis<ema50 and rsi<50: sig='BÄRISCH'
    else: sig='NEUTRAL'
    return sig, preis, rsi

# ===== MENÜ OBEN - Für Handy: oben, nicht links =====
st.title("📈 Trading App")
st.caption("LTC • KSM • XRP • XLM • SHX  |  LONG / SHORT + ABC + Fibo + Score")

col_m1, col_m2 = st.columns(2)
with col_m1:
    coin = st.selectbox("🪙 Coin", ['KSM','LTC','XRP','XLM','SHX'], index=0)
with col_m2:
    timeframe = st.selectbox("⏰ Timeframe", ['15m','1h','1d'], index=2)

col_m3, col_m4 = st.columns(2)
with col_m3:
    einstieg = st.number_input("Dein Einstieg", value=2.60, format="%.4f")
with col_m4:
    st.write("")
    st.write("")
    if st.button("🔄 JETZT SCANNEN"):
        st.rerun()

# ===== DATEN =====
with st.spinner(f"Lade {coin} {timeframe}..."):
    df = hole_kerzen(coin+'USDT', timeframe, 300)
    btc_sig, btc_preis, btc_rsi = hole_btc()

if df is None:
    st.error("❌ Keine Daten - Nochmal auf SCANNEN klicken.")
    st.stop()

closes = df['close'].tolist(); preis = closes[-1]
rsi = berechne_rsi(closes, 14); macd = berechne_macd(closes)
sh, sl, is_up = finde_swing(df, 100)
fibs, diff = berechne_fibos(sh, sl, is_up)
abc = berechne_abc(df); div = berechne_divergenz(closes); sweep = berechne_sweep(df)
vols = df['vol'].tolist(); vol_schnitt = sum(vols[-41:-1])/40 if len(vols)>41 else vols[-1]; vol_jetzt = vols[-1]
if closes[-1]>closes[-2] and vol_jetzt>vol_schnitt*1.2: vol_sig='ECHT ✅'
elif closes[-1]>closes[-2] and vol_jetzt<vol_schnitt*0.8: vol_sig='FAKE ⚠️'
elif closes[-1]<closes[-2] and vol_jetzt>vol_schnitt*1.5: vol_sig='PANIK 🔴'
else: vol_sig='NEUTRAL'

bull, baer = 0, 0
if preis > fibs['0.382']: bull+=1
else: baer+=1
if preis > fibs['0.5']: bull+=1
else: baer+=1
in_golden = min(fibs['0.382'], fibs['0.618']) <= preis <= max(fibs['0.382'], fibs['0.618'])
if in_golden and rsi<45: bull+=1
if in_golden and rsi>55: baer+=1
if rsi<30: bull+=2
elif rsi<40: bull+=1
elif rsi>70: baer+=2
elif rsi>60: baer+=1
if macd>0: bull+=1
else: baer+=1
if bull>=3 and baer<=1: signal='BULLISCH'
elif baer>=3 and bull<=1: signal='BÄRISCH'
else: signal='BODENBILDUNG'

score = 50; details = []
if signal=='BULLISCH': score+=15; details.append('Fibo BULLISCH +15')
if signal=='BÄRISCH': score-=15; details.append('Fibo BÄRISCH -15')
if in_golden and rsi<45: score+=10; details.append('Golden Zone +10')
if in_golden and rsi>55: score-=10; details.append('Golden Zone -10')
if rsi<30: score+=12; details.append('RSI überverkauft +12')
elif rsi<40: score+=6; details.append('RSI tief +6')
elif rsi>70: score-=12; details.append('RSI überkauft -12')
elif rsi>60: score-=6; details.append('RSI hoch -6')
if macd>0: score+=5
else: score-=5
if btc_sig=='BULLISCH': score+=10; details.append('BTC +10')
if btc_sig=='BÄRISCH': score-=10; details.append('BTC -10')
if 'BULLISCHE' in div: score+=12; details.append('Bull. Div. +12')
if 'BÄRISCHE' in div: score-=12; details.append('Bär. Div. -12')
if 'ECHT' in vol_sig: score+=8
if 'FAKE' in vol_sig: score-=10
if 'BULLISH' in sweep: score+=18; details.append('Sweep +18 🔥')
if 'BEARISH' in sweep: score-=18; details.append('Sweep -18 🔥')
if abc: score+=abc['bonus']; details.append(f"ABC {abc['welle']} {abc['bonus']:+d}")
score = max(0, min(100, score))

darf = True; grund_ls = ''
if btc_sig=='BÄRISCH' and signal=='BULLISCH': darf=False; grund_ls='BTC BÄRISCH blockiert LONG. '
if 'FAKE' in vol_sig: darf=False; grund_ls+='Volumen FAKE. '
if abc and 'WELLE B' in abc['welle']: darf=False; grund_ls+='In Welle B - danach kommt C. '
if not darf:
    ls='WARTEN'; ls_grund='Blockiert: '+grund_ls; ls_entry=preis; ls_stop=preis*0.98; ls_target=preis*1.02
elif score>=65 and signal=='BULLISCH':
    ls='LONG'; ls_grund=f'Score {score}/100 + BULLISCH + BTC ok.'; ls_entry=preis; ls_stop=fibs['1']; ls_target=fibs['0.786']
elif score<=35 and signal=='BÄRISCH':
    ls='SHORT'; ls_grund=f'Score {score}/100 + BÄRISCH.'; ls_entry=preis; ls_stop=fibs['0']; ls_target=fibs['1']
elif score>=80:
    ls='LONG'; ls_grund=f'Score {score}/100 = EXTREM STARK.'; ls_entry=preis; ls_stop=fibs['1']; ls_target=fibs['0.618']
elif score<=20:
    ls='SHORT'; ls_grund=f'Score {score}/100 = EXTREM SCHWACH.'; ls_entry=preis; ls_stop=fibs['0']; ls_target=fibs['1']
else:
    ls='WARTEN'; ls_grund=f'Score {score}/100 = Zu schwach für LONG, zu stark für SHORT.'; ls_entry=preis; ls_stop=preis*0.98; ls_target=preis*1.02

# ===== LONG / SHORT BOX - GANZ GROSS =====
if ls=='LONG':
    st.markdown(f"<div style='background:#052e16;border:3px solid #22c55e;border-radius:16px;padding:20px;text-align:center'><div style='font-size:54px;font-weight:900'>🟢 LONG</div><div style='font-size:18px'>KAUFEN</div><div style='margin-top:10px'>{ls_grund}</div></div>", unsafe_allow_html=True)
elif ls=='SHORT':
    st.markdown(f"<div style='background:#450a0a;border:3px solid #ef4444;border-radius:16px;padding:20px;text-align:center'><div style='font-size:54px;font-weight:900'>🔴 SHORT</div><div style='font-size:18px'>VERKAUFEN</div><div style='margin-top:10px'>{ls_grund}</div></div>", unsafe_allow_html=True)
else:
    st.markdown(f"<div style='background:#422006;border:3px solid #facc15;border-radius:16px;padding:20px;text-align:center'><div style='font-size:54px;font-weight:900'>🟡 WARTEN</div><div style='font-size:18px'>FINGER WEG</div><div style='margin-top:10px'>{ls_grund}</div></div>", unsafe_allow_html=True)

st.write("")
c1, c2 = st.columns(2)
c1.metric("🎯 EINTRITT", f"{ls_entry:.4f} $")
c2.metric("🧠 SCORE", f"{score} / 100")
c3, c4 = st.columns(2)
c3.metric("🛑 STOP", f"{ls_stop:.4f} $")
c4.metric("✅ ZIEL", f"{ls_target:.4f} $")
risiko = abs(ls_entry-ls_stop); chancen = abs(ls_target-ls_entry)
crv = chancen/risiko if risiko>0 else 0
st.caption(f"Risiko: {risiko/preis*100:.1f}% | Chance: {chancen/preis*100:.1f}% | Chance/Risiko 1 : {crv:.1f} {'✅ Gut!' if crv>=2 else '🟡 Ok' if crv>=1 else '🔴 Schlecht'}")

st.divider()
st.subheader("📊 RSI + Preis")
st.metric("Preis", f"{preis:.4f} $", delta=f"{(preis-einstieg)/einstieg*100:+.2f}% zu Einstieg")
st.metric("RSI (14)", f"{rsi:.1f}", delta="Überverkauft" if rsi<30 else "Überkauft" if rsi>70 else "Neutral")
st.metric("MACD", f"{macd:.4f}")
st.progress(min(100, max(0, int(rsi)))/100)
st.caption(" | ".join(details))

st.divider()
st.subheader("🔤 ABC-Analyse")
if abc:
    st.write(f"**{abc['welle']}**")
    st.write(abc['fazit'])
    st.write(f"Start {abc['start']['preis']:.4f} $ | A {abc['a']['preis']:.4f} $ | B {abc['b']['preis']:.4f} $ | B holt {abc['retrace']*100:.0f}% zurück")
    st.info(f"🎯 C-Ziele: 0.786 = {abc['z0786']:.4f} $ | 1.0 = {abc['z100']:.4f} $ ⭐ | 1.618 = {abc['z1618']:.4f} $")
else:
    st.write("Kein klares ABC-Muster.")
st.write(f"🔥 {sweep}")
st.write(f"📊 Volumen: {vol_sig} | 🔍 Divergenz: {div}")

st.divider()
st.subheader("₿ BTC + 📐 Fibo")
st.metric("BTC", f"{btc_preis:.0f} $", delta=btc_sig)
st.metric("BTC RSI", f"{btc_rsi:.1f}")
st.write(f"Swing Hoch **{sh:.4f} $** | Swing Tief **{sl:.4f} $** | {'AUF ▲' if is_up else 'AB ▼'}")
st.write(f"Golden Zone **{min(fibs['0.382'], fibs['0.618']):.4f} $ - {max(fibs['0.382'], fibs['0.618']):.4f} $** {'🎯 DU BIST DRIN!' if in_golden else ''}")
for k in ['0','0.236','0.382','0.5','0.618','0.786','1','-0.272','-0.618']:
    mark = "👈 DU BIST HIER" if abs(fibs[k]-preis) < abs(diff)*0.05 else ""
    st.write(f"{k} Fib: **{fibs[k]:.4f} $** {mark}")

st.divider()
st.subheader(f"📐 Chart - {coin} {timeframe.upper()}")
fig = go.Figure(data=[go.Candlestick(x=df['time'].tail(120), open=df['open'].tail(120), high=df['high'].tail(120), low=df['low'].tail(120), close=df['close'].tail(120), name='Preis')])
colors = {'0':'yellow','0.236':'gray','0.382':'blue','0.5':'green','0.618':'orange','0.786':'purple','1':'red','-0.272':'teal','-0.618':'darkred'}
for k, v in fibs.items():
    fig.add_hline(y=v, line_dash="dash", line_color=colors.get(k,'white'), annotation_text=f"{k} = {v:.4f} $")
if abc:
    fig.add_hline(y=abc['z100'], line_dash="dot", line_color="blue", annotation_text=f"ABC C=1.0")
    fig.add_hline(y=abc['z1618'], line_dash="dot", line_color="blue", annotation_text=f"ABC C=1.618")
fig.update_layout(template="plotly_dark", height=450, xaxis_rangeslider_visible=False, title=f"{coin} - {preis:.4f} $ - {ls} - Score {score}")
st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("📊 Alle 5 Coins")
if st.button("🔄 ALLE 5 COINS SCANNEN"):
    rows=[]
    for c in ['LTC','KSM','XRP','XLM','SHX']:
        d2=hole_kerzen(c+'USDT', timeframe, 300)
        if d2 is not None:
            cl=d2['close'].tolist(); r2=berechne_rsi(cl,14)
            rows.append({'Coin':c,'Preis':f"{cl[-1]:.4f} $",'RSI':f"{r2:.1f}",'Status':'🟢 Überverkauft' if r2<30 else '🔴 Überkauft' if r2>70 else '⚪ Neutral'})
    st.table(pd.DataFrame(rows))
st.caption("⚠️ Keine Finanzberatung - Immer Stop setzen!")
