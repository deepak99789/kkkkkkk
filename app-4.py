# supply_demand_screener_streamlit.py
# Streamlit app: Supply & Demand screener (3-candle or n-base)
# - Yahoo Finance (yfinance)
# - Rally/Drop: body >= 80% of range
# - Base: body <= 50% of range
# - Entry/SL/Target with RR = 1:5
# - Shows LegOut Time (only)
# - Built-in NIFTY50 list; upload CSV for larger universes if needed

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import time

st.set_page_config(page_title="Supply & Demand Screener", layout="wide")

# --------------------------
# Helper functions
# --------------------------
@st.cache_data(ttl=300)
def fetch_ohlcv(symbol: str, period: str, interval: str):
    """
    Fetch OHLCV using yfinance. Return DataFrame with Datetime index and columns Open, High, Low, Close, Volume.
    """
    try:
        # yfinance uses interval strings like '1m','5m','15m','60m','1d','1wk'
        df = yf.download(symbol, period=period, interval=interval, progress=False, threads=False)
        if df is None or df.empty:
            return None
        df = df[['Open','High','Low','Close','Volume']].copy()
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return None

def candle_body_ratio(o, h, l, c):
    rng = (h - l)
    if rng == 0:
        return 0.0
    body = abs(c - o)
    return body / rng

def get_candle_label(o, h, l, c, rally_thresh=0.8, base_thresh=0.5):
    """
    Returns one of: 'Rally', 'Drop', 'Base', 'Other'
    """
    body_pct = candle_body_ratio(o, h, l, c)
    if c > o and body_pct >= rally_thresh:
        return "Rally"
    if c < o and body_pct >= rally_thresh:
        return "Drop"
    if body_pct <= base_thresh:
        return "Base"
    return "Other"

def detect_patterns(df: pd.DataFrame, base_count=1, rally_thresh=0.8, base_thresh=0.5):
    """
    Scans df (index = Datetime) for patterns with sliding window:
      LegIn (index i) - Base candles (i+1 ... i+base_count) - LegOut (i+base_count+1)
    Returns list of dicts with Pattern, Zone, LegOut Time, Entry, StopLoss, Target, start/end indices.
    """
    patterns = []
    n = base_count + 2
    total = len(df)
    if total < n:
        return patterns

    # Precompute labels to avoid repeated calls
    labels = []
    for idx, row in df.iterrows():
        labels.append(get_candle_label(row['Open'], row['High'], row['Low'], row['Close'],
                                       rally_thresh=rally_thresh, base_thresh=base_thresh))

    for i in range(0, total - n + 1):
        leg_in_label = labels[i]
        base_slice = df.iloc[i+1 : i+1+base_count]
        # If base_slice is empty skip
        if base_slice.empty:
            continue
        # Check base candles are all 'Base'
        base_valid = all(
            get_candle_label(r.Open, r.High, r.Low, r.Close, rally_thresh, base_thresh) == "Base"
            for r in base_slice.itertuples()
        )
        if not base_valid:
            continue

        legout_index = i + 1 + base_count
        leg_out_label = labels[legout_index]

        # Determine pattern
        pattern = None
        zone = None
        base_high = float(base_slice['High'].max())
        base_low = float(base_slice['Low'].min())

        if leg_in_label == "Rally" and leg_out_label == "Rally":
            pattern = "RBR"
            zone = "Demand"
            entry = base_high
            sl = base_low
        elif leg_in_label == "Rally" and leg_out_label == "Drop":
            pattern = "RBD"
            zone = "Supply"
            entry = base_low
            sl = base_high
        elif leg_in_label == "Drop" and leg_out_label == "Drop":
            pattern = "DBD"
            zone = "Supply"
            entry = base_low
            sl = base_high
        elif leg_in_label == "Drop" and leg_out_label == "Rally":
            pattern = "DBR"
            zone = "Demand"
            entry = base_high
            sl = base_low
        else:
            continue

        # Risk and target: RR 1:5
        risk = abs(entry - sl)
        if risk == 0:
            # skip degenerate zones
            continue
        if zone == "Demand":
            target = entry + (risk * 5)
        else:
            target = entry - (risk * 5)

        patterns.append({
            "pattern": pattern,
            "zone": zone,
            "legout_time": df.index[legout_index],
            "entry": round(float(entry), 2),
            "sl": round(float(sl), 2),
            "target": round(float(target), 2),
            "start_index": i,
            "end_index": i + n - 1
        })
    return patterns

def evaluate_zone_status(df: pd.DataFrame, pattern: dict):
    """
    After the pattern's LegOut candle, check subsequent candles to determine:
      - Target (if target price touched)
      - Stoploss (if SL touched)
      - EntryTaken (if entry touched)
      - Fresh (if none touched yet)
    Returns one of: 'Target','Stoploss','EntryTaken','Fresh'
    """
    end_idx = pattern['end_index']
    afterward = df.iloc[end_idx+1 :]
    if afterward.empty:
        return "Fresh"
    entry = pattern['entry']
    sl = pattern['sl']
    target = pattern['target']
    zone = pattern['zone']

    hit_entry = False; hit_sl = False; hit_target = False
    for _, r in afterward.iterrows():
        high = r['High']; low = r['Low']
        # All comparisons are inclusive (touch = hit)
        if low <= target <= high:
            hit_target = True
            break  # target is highest priority
        if low <= sl <= high:
            hit_sl = True
            break
        if low <= entry <= high:
            hit_entry = True
            # don't break; maybe SL/Target later
    if hit_target:
        return "Target"
    if hit_sl:
        return "Stoploss"
    if hit_entry:
        return "EntryTaken"
    return "Fresh"

# --------------------------
# Stock universes (hard-coded)
# NIFTY50 is complete. For large universes you can upload CSV if you want exact official lists.
# --------------------------

NIFTY50 = [
    "ADANIENT.NS","ASIANPAINT.NS","AXISBANK.NS","BAJAJ-AUTO.NS","BAJAJFINSV.NS","BAJFINANCE.NS",
    "BHARTIARTL.NS","BRITANNIA.NS","CIPLA.NS","COALINDIA.NS","DIVISLAB.NS","DRREDDY.NS",
    "EICHERMOT.NS","GRASIM.NS","HCLTECH.NS","HDFCBANK.NS","HDFC.NS","HDFCLIFE.NS",
    "HINDALCO.NS","HINDUNILVR.NS","ICICIBANK.NS","INDUSINDBK.NS","INFY.NS","IOC.NS",
    "ITC.NS","JSWSTEEL.NS","KOTAKBANK.NS","LT.NS","M&M.NS","MARUTI.NS",
    "NESTLEIND.NS","NTPC.NS","ONGC.NS","POWERGRID.NS","RELIANCE.NS","SBILIFE.NS",
    "SBIN.NS","SUNPHARMA.NS","TATACHEM.NS","TATACONSUM.NS","TATAMOTORS.NS","TATASTEEL.NS",
    "TCS.NS","TECHM.NS","TITAN.NS","ULTRACEMCO.NS","UPL.NS","WIPRO.NS"
]

# For larger universes we provide a reasonable default set (but you can upload CSV to replace)
# To avoid rate limits / long run times, prefer uploading a CSV for NIFTY100 / 200 / 500.
DEFAULT_LARGE = NIFTY50.copy()  # fallback

stock_universe = {
    "NIFTY50": NIFTY50,
    "NIFTY100 (upload CSV if you want full exact list)": DEFAULT_LARGE,
    "NIFTY200 (upload CSV if you want full exact list)": DEFAULT_LARGE,
    "NIFTY500 (upload CSV if you want full exact list)": DEFAULT_LARGE,
    "Upload my tickers (CSV)": []
}

# --------------------------
# UI
# --------------------------
st.title("Supply & Demand Screener — Yahoo Finance")
st.markdown("Rules: Rally/Drop body >= 80% of candle range; Base body <= 50% of range. Risk:Reward = 1:5. Only LegOut Time shown in results.")

with st.sidebar:
    st.header("Scan Settings")
    script_type = st.selectbox("Select Script Type / Universe", list(stock_universe.keys()))
    base_count = st.slider("Number of Base Candles", min_value=1, max_value=6, value=1)
    # Intervals commonly supported by yfinance:
    interval = st.selectbox("Select Time Interval", ['1m','5m','15m','30m','60m','75m','125m','1h','2h','4h','1d','1wk'], index=2)
    period = st.selectbox("Data Period to Fetch (yfinance)", ['7d','30d','60d','90d','180d','1y'], index=1)
    zone_status_sel = st.multiselect("Zone Status (filter)", ['Fresh','EntryTaken','Target','Stoploss'], default=['Fresh','EntryTaken','Target','Stoploss'])
    zone_type_sel = st.multiselect("Zone Type (filter)", ['Supply','Demand','All'], default=['Supply','Demand'])
    include_alerts = st.checkbox("Include Alerts (visual, in-app)", value=True)
    upload_csv = None
    if script_type.startswith("NIFTY100") or script_type.startswith("NIFTY200") or script_type.startswith("NIFTY500") or script_type.startswith("Upload my"):
        upload_csv = st.file_uploader("Upload CSV with tickers (one per line, e.g. TCS.NS). If provided, will replace the universe.", type=['csv','txt'])

scan_btn = st.button("🔍 Run Scan")

# Prepare ticker list
tickers = []
if script_type == "Upload my tickers (CSV)" and upload_csv is not None:
    try:
        df_up = pd.read_csv(upload_csv, header=None)
        tickers = df_up[0].astype(str).tolist()
    except Exception:
        st.error("Couldn't read uploaded CSV. Make sure it contains one ticker per line (e.g. TCS.NS).")
elif upload_csv is not None and script_type.startswith("NIFTY"):
    # user uploaded CSV to replace default for larger universes
    try:
        df_up = pd.read_csv(upload_csv, header=None)
        tickers = df_up[0].astype(str).tolist()
    except Exception:
        st.error("Couldn't read uploaded CSV. Falling back to default small universe.")
        tickers = stock_universe.get(script_type, DEFAULT_LARGE)
else:
    tickers = stock_universe.get(script_type, DEFAULT_LARGE)

if not tickers:
    st.warning("Ticker list is empty. Upload a CSV or choose a universe with tickers.")
    st.stop()

# Run scan
if scan_btn:
    st.info(f"Starting scan for {len(tickers)} tickers — this may take time. Be aware of yfinance rate limits for large lists.")
    results = []
    progress = st.progress(0)
    total = len(tickers)
    for idx, sym in enumerate(tickers):
        try:
            df = fetch_ohlcv(sym, period=period, interval=interval)
            if df is None or df.empty:
                # skip if no data
                progress.progress(int((idx+1)/total*100))
                time.sleep(0.01)
                continue

            patterns = detect_patterns(df, base_count=base_count, rally_thresh=0.8, base_thresh=0.5)
            for p in patterns:
                # evaluate status using the df (pattern contains indices)
                status = evaluate_zone_status(df, p)
                # Apply filters
                if ('All' not in zone_type_sel) and (p['zone'] not in zone_type_sel):
                    continue
                if status not in zone_status_sel:
                    continue
                results.append({
                    "symbol": sym,
                    "pattern": p['pattern'],
                    "zone": p['zone'],
                    "legout_time": pd.to_datetime(p['legout_time']),
                    "entry": p['entry'],
                    "sl": p['sl'],
                    "target": p['target'],
                    "status": status
                })
        except Exception as e:
            # skip on exception for this symbol
            # For debugging uncomment:
            # st.write(f"Error {sym}: {e}")
            pass
        progress.progress(int((idx+1)/total*100))
        # small sleep to avoid hammering
        time.sleep(0.05)
    progress.empty()

    if not results:
        st.warning("No zones found for selected universe / filters.")
    else:
        df_res = pd.DataFrame(results)
        # Sort by most recent legout_time
        df_res = df_res.sort_values('legout_time', ascending=False).reset_index(drop=True)
        # Format legout_time for display
        df_res['legout_time'] = df_res['legout_time'].dt.strftime("%Y-%m-%d %H:%M:%S")
        # Display table with color coding
        def color_zone(row):
            if row['zone'] == 'Demand':
                return ['background-color: #e9fff0'] * len(row)
            else:
                return ['background-color: #fff0f0'] * len(row)

        display_cols = ['symbol','pattern','zone','legout_time','entry','sl','target','status']
        st.subheader(f"Scan Results — {len(df_res)} zones found")
        st.dataframe(df_res[display_cols])

        # Alerts / textual suggestions
        if include_alerts:
            st.markdown("### Alerts / Suggestions")
            for _, r in df_res.iterrows():
                sym = r['symbol']; zt = r['zone']; stt = r['status']
                entry = r['entry']; sl = r['sl']; tgt = r['target']
                if stt == 'Fresh':
                    st.info(f"{sym} — {r['pattern']} ({zt}) — Fresh. Entry: {entry}, SL: {sl}, Target(1:5): {tgt}")
                elif stt == 'EntryTaken':
                    st.success(f"{sym} — Entry touched. Manage trade. Entry: {entry}, SL: {sl}, Target: {tgt}")
                elif stt == 'Target':
                    st.success(f"{sym} — Target reached previously.")
                elif stt == 'Stoploss':
                    st.error(f"{sym} — Stoploss hit.")

        # Download button
        csv = df_res.to_csv(index=False)
        st.download_button("Download results as CSV", data=csv, file_name="supply_demand_scan_results.csv", mime="text/csv")

st.markdown("---")
st.markdown("**Notes:**\n\n- For large universes (NIFTY100/200/500) uploading an exact CSV of tickers (one-per-line) is recommended to avoid rate limits and speed up scans. \n- YFinance may not provide intraday data older than a few weeks for certain intervals. Use appropriate `period` with `interval`.\n- This scanner uses inclusive touch checks: if price touches entry/sl/target on a candle's high/low, it is considered hit.\n- If you want automatic alerts (Telegram / email), I can add options to send messages when patterns appear or when price touches entry/SL/target.\n")

