import streamlit as st
import feedparser
import sqlite3
import pandas as pd
from rapidfuzz import fuzz
from streamlit_autorefresh import st_autorefresh
import time

# --- APP CONFIG & AUTO-REFRESH ---
st.set_page_config(page_title="ReadyNews Dashboard", layout="wide")
st_autorefresh(interval=900000, key="freshen_news") # 15 min refresh

# CSS to force smaller font size (approx 12pt) for the whole table
st.markdown("""
    <style>
    [data-testid="stTable"] { font-size: 12px !important; }
    div[data-testid="stExpander"] p { font-size: 12px; }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect('feeds.db', check_same_thread=False)
    c = conn.cursor()
    # Migration: Ensure 'label' column exists instead of 'category'
    c.execute('CREATE TABLE IF NOT EXISTS feeds (id INTEGER PRIMARY KEY, url TEXT, label TEXT)')
    conn.commit()
    return conn

conn = init_db()

def add_feed(url, label):
    c = conn.cursor()
    c.execute('INSERT INTO feeds (url, label) VALUES (?, ?)', (url, label))
    conn.commit()

def delete_feed(id):
    c = conn.cursor()
    c.execute('DELETE FROM feeds WHERE id = ?', (id,))
    conn.commit()

def get_feeds():
    c = conn.cursor()
    c.execute('SELECT * FROM feeds')
    return c.fetchall()

# --- CONTENT FETCHING ---
@st.cache_data(ttl=900)
def fetch_news(feeds):
    rows = []
    seen_titles = []
    
    for _, url, label in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get('title', 'No Title')
                
                # Deduplication logic (85% similarity)
                if not any(fuzz.ratio(title.lower(), s.lower()) > 85 for s in seen_titles):
                    rows.append({
                        "Source": label,
                        "Headline": title,
                        "Link": entry.get('link', '#'),
                        "Date/Time": entry.get('published', 'Recently')
                    })
                    seen_titles.append(title)
        except:
            continue
            
    return pd.DataFrame(rows)

# --- SIDEBAR: SOURCE MANAGEMENT ---
with st.sidebar:
    st.header("⚙️ Sources")
    with st.expander("➕ Add New Source"):
        new_label = st.text_input("Source Name (e.g. ARERA Gas)")
        new_url = st.text_input("RSS/Google Alert URL")
        if st.button("Save Source"):
            if new_label and new_url:
                add_feed(new_url, new_label)
                st.rerun()

    st.divider()
    feeds = get_feeds()
    for fid, furl, flabel in feeds:
        col1, col2 = st.columns([4, 1])
        col1.caption(f"**{flabel}**")
        if col2.button("🗑️", key=f"del_{fid}"):
            delete_feed(fid)
            st.rerun()

# --- MAIN DASHBOARD ---
st.title("🗞️ ReadyNews Intelligence")
st.caption(f"Dashboard Refreshed: {time.strftime('%H:%M:%S')}")

if not feeds:
    st.info("Sidebar: Add your first source and name it to start.")
else:
    df = fetch_news(feeds)
    
    if not df.empty:
        # Display as an interactive, compact table
        st.data_editor(
            df,
            column_config={
                "Headline": st.column_config.LinkColumn(
                    "Headline",
                    help="Click to open news",
                    validate="^http",
                    display_text=".*", # Shows the full headline as the link
                ),
                "Source": st.column_config.TextColumn("Source", width="medium"),
                "Date/Time": st.column_config.TextColumn("Date/Time", width="small"),
                "Link": None # Hide the raw URL column
            },
            hide_index=True,
            use_container_width=True,
            disabled=True, # Makes it view-only
            height=800 # Large height to show many news items at once
        )
    else:
        st.write("No news found yet.")
