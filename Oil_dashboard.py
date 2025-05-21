import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import requests
import pandas as pd
from datetime import datetime

# --- API KEYS ---
EIA_API_KEY = "Kg4bRTvallayw3EcBdRD79BJCC3Lour0ek7Ngo6X"
NEWS_API_KEY = "467f8863719649619570a7ec9338c2c1"


# --- STREAMLIT PAGE CONFIG ---
st.set_page_config(page_title="🛢️ Oil Monitor", layout="wide")
st.title("🛢️ Oil Market Monitor")
st.markdown("Live oil prices, key market data, and energy intelligence.")

# --- TIMEFRAME SELECTOR MAPPING ---
timeframes = {
    "5D": ("5d", "1h"),
    "1M": ("1mo", "1d"),
    "1Y": ("1y", "1wk")
}


# --- PRICE FETCHING + METRICS ---
def get_oil_price(ticker, period="5d", interval="1d"):
    data = yf.download(ticker, period=period, interval=interval, progress=False)
    if data.empty or 'Close' not in data.columns:
        return None, None, pd.DataFrame()
    
    first_valid = data['Close'].dropna().iloc[0]
    last_valid = data['Close'].dropna().iloc[-1]
    change = ((last_valid - first_valid) / first_valid) * 100

    return float(last_valid), float(change), data



# --- PLOTLY CHART FUNCTION ---
def plot_line_chart(df, title, y_title="Price (USD)"):
    if df is None or df.empty:
        st.warning(f"No data available for {title}")
        return

    # Flatten multi-index columns if needed
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ['_'.join([str(level) for level in col if level]) for col in df.columns.values]

    # Identify a likely 'Close' column
    close_col = None
    for col in df.columns:
        if isinstance(col, tuple):
            col = '_'.join(str(c) for c in col if c)
        col_str = str(col).lower()
        if "close" in col_str or col_str in ["bz=f.3", "cl=f.3"]:
            close_col = col
            break

    if not close_col or df[close_col].dropna().empty:
        st.warning(f"No valid 'Close' column found for {title}")
        return

    # Fix datetime column and set as index
    datetime_col = None
    for col in ["Date", "Datetime", "date", "datetime"]:
        if col in df.columns:
            datetime_col = col
            break

    if datetime_col:
        df[datetime_col] = pd.to_datetime(df[datetime_col])
        df.set_index(datetime_col, inplace=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df[close_col], mode='lines', name=title))
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y_title,
        height=350,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)


# --- EIA DATA FETCH FUNCTION ---
def get_eia_series(series_id):
    url = f"https://api.eia.gov/v2/seriesid/{series_id}?api_key={EIA_API_KEY}"
    response = requests.get(url)
    try:
        data = response.json()
        if "response" not in data or "data" not in data["response"]:
            raise ValueError(data.get("error", "No 'data' in response."))

        records = data["response"]["data"]
        if not records:
            raise ValueError("No data records returned.")
        
        df = pd.DataFrame(records)
        if "period" not in df.columns or "value" not in df.columns:
            raise ValueError("Expected 'period' and 'value' columns missing.")

        df["Date"] = pd.to_datetime(df["period"])
        df = df.sort_values("Date")
        df = df[["Date", "value"]].rename(columns={"value": "Value"}).set_index("Date")
        return df
    except Exception as e:
        st.error(f"❌ EIA API Error for series '{series_id}': {e}")
        return pd.DataFrame()




# --- NEWS FROM YFINANCE + NEWSAPI ---
def get_news(debug=False):
    keywords = [
        "oil", "crude", "brent", "WTI", "OPEC", "barrel", "refinery", 
        "fossil", "diesel", "gasoline", "energy", "production", "supply", "pipeline"
    ]
    
    news_items = []

    # --- Primary: NewsAPI ---
    try:
        url = (
            f"https://newsapi.org/v2/everything?"
            f"q=oil+OR+brent+OR+opec+OR+crude&language=en&sortBy=publishedAt&pageSize=10&apiKey={NEWS_API_KEY}"
        )
        response = requests.get(url)
        data = response.json()

        if debug:
            st.write("NewsAPI status:", response.status_code)
            st.write("Raw NewsAPI response:", data)

        if response.status_code == 200:
            articles = data.get("articles", [])
            for a in articles:
                text_blob = (a.get("title", "") + " " + a.get("description", "")).lower()
                if any(kw.lower() in text_blob for kw in keywords):
                    news_items.append({
                        "title": a["title"],
                        "link": a["url"],
                        "publisher": a["source"]["name"],
                        "time": a["publishedAt"],
                        "desc": a.get("description", "")
                    })

    except Exception as e:
        if debug:
            st.warning(f"NewsAPI fetch failed: {e}")

    # --- Fallback: yfinance ---
    if not news_items:
        try:
            fallback_news = yf.Ticker("BZ=F").news[:5]
            for item in fallback_news:
                news_items.append({
                    "title": item["title"],
                    "link": item["link"],
                    "publisher": item.get("publisher", "Unknown"),
                    "time": item.get("providerPublishTime", "N/A"),
                    "desc": item.get("summary", "")
                })
            if debug:
                st.write("Used yfinance fallback")
        except Exception as e:
            if debug:
                st.warning(f"yfinance fallback failed: {e}")

    return news_items






# --- MAIN APP LAYOUT ---

st.subheader("📈 Live Oil Prices")

# --- BRENT SECTION ---
st.subheader("🛢️ Brent Crude")

brent_price, brent_change, _ = get_oil_price("BZ=F", "5d", "1d")
if brent_price:
    st.metric("Brent Price", f"${brent_price:.2f}", f"{brent_change:.2f}%")

brent_tf = st.radio("Brent timeframe:", list(timeframes.keys()), horizontal=True, key="brent")
brent_period, brent_interval = timeframes[brent_tf]
brent_df = yf.download("BZ=F", period=brent_period, interval=brent_interval, progress=False)
plot_line_chart(brent_df, f"Brent Crude ({brent_tf})")


# --- WTI SECTION ---
st.subheader("🛢️ WTI Crude")

wti_price, wti_change, _ = get_oil_price("CL=F", "5d", "1d")
if wti_price:
    st.metric("WTI Price", f"${wti_price:.2f}", f"{wti_change:.2f}%")

wti_tf = st.radio("WTI timeframe:", list(timeframes.keys()), horizontal=True, key="wti")
wti_period, wti_interval = timeframes[wti_tf]
wti_df = yf.download("CL=F", period=wti_period, interval=wti_interval, progress=False)
plot_line_chart(wti_df, f"WTI Crude ({wti_tf})")



# --- NEWS SECTION ---
st.subheader("📰 Top Oil-Related News")

news_items = get_news(debug=False)

if not news_items:
    st.info("No relevant oil news articles found right now. Try again later.")
else:
    for item in news_items:
        st.markdown(f"**[{item['title']}]({item['link']})**")
        st.markdown(f"*{item['publisher']} - {item['time'][:10]}*")
        if item['desc']:
            st.markdown(item['desc'])
        st.markdown("---")



# --- EIA DATA SECTION ---
st.subheader("📊 U.S. Energy Information Administration (EIA) Data")

eia_series = {
    "U.S. Commercial Crude Oil Stocks": "PET.WCESTUS1.W",
    "U.S. Net Crude Imports": "PET.WCRNTUS2.W",
    # New working series for U.S. crude field production
    "U.S. Field Production of Crude Oil": "PET.MCRFPUS2.M"
}

eia_range = st.radio("Select EIA Date Range:", ["5Y", "10Y", "All"], horizontal=True)

for label, series_id in eia_series.items():
    df = get_eia_series(series_id)

    if not df.empty:
        if eia_range == "5Y":
            df = df[df.index >= pd.Timestamp.now() - pd.DateOffset(years=5)]
        elif eia_range == "10Y":
            df = df[df.index >= pd.Timestamp.now() - pd.DateOffset(years=10)]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df["Value"], mode="lines", name=label))
        fig.update_layout(
            title=label,
            xaxis_title="Date",
            yaxis_title="Million Barrels",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"No data available for {label}")




