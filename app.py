
import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Market Pulse", layout="wide")
st.title("Market Pulse - SEC + News + X")

left, right = st.columns([2,1])

with left:
    st.subheader("Headline Sentiment (scored)")
    if os.path.exists("data/news_scored.csv"):
        df = pd.read_csv("data/news_scored.csv")
        st.dataframe(df[["ticker","published","title","sentiment","link"]])
    else:
        st.info("Run `python run_once.py` first to fetch and score headlines.")

with right:
    st.subheader("Composite Scores")
    if os.path.exists("data/pulse_scores.csv"):
        s = pd.read_csv("data/pulse_scores.csv")
        st.bar_chart(s.set_index("ticker")["score"])
        st.dataframe(s)
    else:
        st.info("No scores yet - run `python run_once.py`.")
