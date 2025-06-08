
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import google.generativeai as genai
import tempfile
import os
import json
from datetime import datetime, timedelta

GOOGLE_API_KEY = st.secrets["google"]["api_key"]
genai.configure(api_key=GOOGLE_API_KEY)

MODEL_NAME = 'gemini-2.0-flash' 
gen_model = genai.GenerativeModel(MODEL_NAME)


st.set_page_config(layout="wide")
st.title("ChartMind: AI-Powered Visual Stock Analyser")
st.markdown(
    '<p style="font-size:20px; font-weight:500; color:gray;">Decode market movements with technical indicators and Google Gemini-driven insights.</p>',
    unsafe_allow_html=True
)

with st.sidebar:


   
    st.write("`Created by:`")

    linkedin_url = "https://www.linkedin.com/in/tushar-yadav-6871a51b9/"
    x_url = "https://x.com/wildtummy_" 
    github_url = "https://github.com/Wildtummy" 

    st.markdown(f"""
    <div style="font-size: 1.8rem; font-weight: 700; margin-bottom: 6px;">Tushar Yadav</div>

    <div style="margin-bottom: 30px;">
    <a href="{linkedin_url}" target="_blank" style="margin-right: 15px;">
        <img src="https://cdn-icons-png.flaticon.com/512/174/174857.png" width="30" height="30" alt="LinkedIn" />
    </a>
    <a href="{x_url}" target="_blank" style="margin-right: 15px;">
        <img src="https://cdn-icons-png.flaticon.com/512/733/733579.png" width="30" height="30" alt="X" />
    </a>
    <a href="{github_url}" target="_blank">
        <img src="https://cdn-icons-png.flaticon.com/512/733/733553.png" width="30" height="30" alt="GitHub" />
    </a>
    </div>
    """, unsafe_allow_html=True)
st.sidebar.header("Configuration")


tickers_input = st.sidebar.text_input("Enter Stock Tickers (comma-separated):", "AAPL,MSFT,GOOG")

tickers = [ticker.strip().upper() for ticker in tickers_input.split(",") if ticker.strip()]


end_date_default = datetime.today()
start_date_default = end_date_default - timedelta(days=365)
start_date = st.sidebar.date_input("Start Date", value=start_date_default)
end_date = st.sidebar.date_input("End Date", value=end_date_default)

# Technical indicators 
st.sidebar.subheader("Technical Indicators")
indicators = st.sidebar.multiselect(
    "Select Indicators:",
    ["20-Day SMA", "20-Day EMA", "20-Day Bollinger Bands", "VWAP"],
    default=["20-Day SMA"]
)

# fetch data 
if st.sidebar.button("Fetch Data"):
    stock_data = {}
    for ticker in tickers:
        
        data = yf.download(ticker, start=start_date, end=end_date,multi_level_index=False)
        if not data.empty:
            stock_data[ticker] = data
        else:
            st.warning(f"No data found for {ticker}.")
    st.session_state["stock_data"] = stock_data
    st.success("Stock data loaded successfully for: " + ", ".join(stock_data.keys()))


if "stock_data" in st.session_state and st.session_state["stock_data"]:

     # Candlestick chart 
    def analyze_ticker(ticker, data):
       
        fig = go.Figure(data=[
            go.Candlestick(
                x=data.index,
                open=data['Open'],
                high=data['High'],
                low=data['Low'],
                close=data['Close'],
                name="Candlestick"
            )
        ])

        # technical indicators
        def add_indicator(indicator):
            if indicator == "20-Day SMA":
                sma = data['Close'].rolling(window=20).mean()
                fig.add_trace(go.Scatter(x=data.index, y=sma, mode='lines', name='SMA (20)',line=dict(dash='dot')))
            elif indicator == "20-Day EMA":
                ema = data['Close'].ewm(span=20).mean()
                fig.add_trace(go.Scatter(x=data.index, y=ema, mode='lines', name='EMA (20)',line=dict(dash='dot')))
            elif indicator == "20-Day Bollinger Bands":
                sma = data['Close'].rolling(window=20).mean()
                std = data['Close'].rolling(window=20).std()
                bb_upper = sma + 2 * std
                bb_lower = sma - 2 * std
                fig.add_trace(go.Scatter(x=data.index, y=bb_upper, mode='lines', name='BB Upper',line=dict(dash='dot')))
                fig.add_trace(go.Scatter(x=data.index, y=bb_lower, mode='lines', name='BB Lower',line=dict(dash='dot')))
            elif indicator == "VWAP":
                data['VWAP'] = (data['Close'] * data['Volume']).cumsum() / data['Volume'].cumsum()
                fig.add_trace(go.Scatter(x=data.index, y=data['VWAP'], mode='lines', name='VWAP',line=dict(dash='dot')))
        for ind in indicators:
            add_indicator(ind)
        fig.update_layout(  xaxis_rangeslider_visible=False, dragmode='pan' )


        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
            fig.write_image(tmpfile.name)
            tmpfile_path = tmpfile.name
        with open(tmpfile_path, "rb") as f:
            image_bytes = f.read()
        os.remove(tmpfile_path)

        
        image_part = {
            "data": image_bytes,  
            "mime_type": "image/png"
        }

        #  prompt 
        analysis_prompt = f"""
You are a Stock Trader specializing in Technical Analysis at a top financial institution.

Analyze the stock chart for {ticker} based on its candlestick chart and the displayed technical indicators and include the company name (not just the ticker symbol).

Provide a detailed technical analysis that includes the following:
1. Identification of key candlestick patterns (e.g., doji, hammer, engulfing).
2. Description of recent trend direction (uptrend, downtrend, consolidation).
3. Explanation of how each selected indicator (e.g., SMA, EMA, Bollinger Bands, VWAP) supports or contradicts the trend.
4. Commentary on volume behavior and whether it confirms or diverges from the price movement.
5. Mention any potential breakout or reversal zones.
6. Risk assessment: highlight any conflicting signals or uncertainty factors.

Base your recommendation only on the chart and these factors.

Return your output as a JSON object with three keys:
- 'action': recommendation such as 'Strong Buy', 'Hold', etc.
- 'justification': a detailed multi-paragraph explanation.

Write the justification as if preparing a research note for a senior portfolio manager.
"""


       
        contents = [
            {"role": "user", "parts": [analysis_prompt]},  
            {"role": "user", "parts": [image_part]}       
        ]

        response = gen_model.generate_content(
            contents=contents  
        )

        try:

            result_text = response.text

            json_start_index = result_text.find('{')
            json_end_index = result_text.rfind('}') + 1  # +1 to include the closing brace
            if json_start_index != -1 and json_end_index > json_start_index:
                json_string = result_text[json_start_index:json_end_index]
                result = json.loads(json_string)
            else:
                raise ValueError("No valid JSON object found in the response")

        except json.JSONDecodeError as e:
            result = {"action": "Error", "justification": f"JSON Parsing error: {e}. Raw response text: {response.text}"}
        except ValueError as ve:
            result = {"action": "Error", "justification": f"Value Error: {ve}. Raw response text: {response.text}"}
        except Exception as e:
            result = {"action": "Error", "justification": f"General Error: {e}. Raw response text: {response.text}"}

        return fig, result

    
    tab_names =   list(st.session_state["stock_data"].keys()) 
    tabs = st.tabs(tab_names)

  
    overall_results = []


    for i, ticker in enumerate(st.session_state["stock_data"]):
        data = st.session_state["stock_data"][ticker]
        
        fig, result = analyze_ticker(ticker, data)
        overall_results.append({"Stock": ticker, "Recommendation": result.get("action", "N/A")})
        # ticker-specific tab
        with tabs[i]:
            st.subheader(f"Analysis for {ticker}")
            st.plotly_chart(fig)
            st.write("**Detailed Justification:**")
            st.write(result.get("justification", "No justification provided."))


else:
    st.info("Please fetch stock data using the sidebar.")
