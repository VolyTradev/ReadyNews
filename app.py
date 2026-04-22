import streamlit as st
import feedparser
import sqlite3
from rapidfuzz import fuzz
from streamlit_autorefresh import st_autorefresh
import time

# --- APP CONFIG & AUTO-REFRESH ---
st.set_page_config(page_title="Personal News Hub", layout="wide", initial_sidebar_state="expanded")

# This component handles the background refresh (every 15 minutes)
st_autorefresh(interval=900000, key="freshen_news")

# --- DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect('feeds.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS feeds (id INTEGER PRIMARY KEY, url TEXT, category TEXT)')
    conn.commit()
    return conn

conn = init_db()

def add_feed(url, cat):
    c = conn.cursor()
    c.execute('INSERT INTO feeds (url, category) VALUES (?, ?)', (url, cat))
    conn.commit()

def delete_feed(id):
    c = conn.cursor()
    c.execute('DELETE FROM feeds WHERE id = ?', (id,))
    conn.commit()

def get_feeds():
    c = conn.cursor()
    c.execute('SELECT * FROM feeds')
    return c.fetchall()

# --- CONTENT FETCHING (WITH CACHING) ---
@st.cache_data(ttl=900)  # Cache for 15 mins to keep it fast
def fetch_news(feeds):
    results = []
    seen_titles = []
    
    for _, url, category in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get('title', 'No Title')
                
                # Deduplication logic: skip if title is 85% similar to one we've seen
                is_duplicate = False
                for seen in seen_titles:
                    if fuzz.ratio(title.lower(), seen.lower()) > 85:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    results.append({
                        'title': title,
                        'link': entry.get('link', '#'),
                        'summary': entry.get('summary', 'No summary available.'),
                        'published': entry.get('published', 'Recently'),
                        'category': category
                    })
                    seen_titles.append(title)
        except Exception:
            continue
            
    return results

# --- SIDEBAR: SOURCE MANAGEMENT ---
with st.sidebar:
    st.header("⚙️ Sources")
    
    with st.expander("➕ Add New Source"):
        url_input = st.text_input("RSS or Google Alert URL")
        cat_input = st.selectbox("Category", ["Energy", "Crypto", "Legal", "General"])
        if st.button("Add"):
            if url_input:
                add_feed(url_input, cat_input)
                st.rerun()

    st.divider()
    st.subheader("Current Feeds")
    feeds = get_feeds()
    for fid, furl, fcat in feeds:
        col1, col2 = st.columns([4, 1])
        col1.caption(f"**{fcat}**: {furl[:30]}...")
        if col2.button("🗑️", key=f"del_{fid}"):
            delete_feed(fid)
            st.rerun()

# --- MAIN DASHBOARD ---
st.title("🗞️ Personal News Intelligence")
st.caption(f"Last updated: {time.strftime('%H:%M:%S')}")

if not feeds:
    st.info("Your dashboard is empty. Add your Google Alert or RSS links in the sidebar to begin.")
else:
    all_articles = fetch_news(feeds)
    categories = sorted(list(set([f[2] for f in feeds])))
    
    tabs = st.tabs(categories)
    
    for i, cat in enumerate(categories):
        with tabs[i]:
            cat_articles = [a for a in all_articles if a['category'] == cat]
            if not cat_articles:
                st.write("No news found for this category.")
            else:
                for art in cat_articles[:20]:
                    with st.container():
                        st.markdown(f"### [{art['title']}]({art['link']})")
                        st.caption(f"📅 {art['published']}")
                        # Clean HTML tags from summary if they exist
                        summary_text = art['summary']
                        if '<' in summary_text:
                            summary_text = summary_text.split('<')[0]
                        st.write(summary_text[:300] + "...")
                        st.divider()
