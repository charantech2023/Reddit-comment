# streamlit_app.py
import os
import re
import requests
import streamlit as st
import google.generativeai as genai

# ---------------- Config ----------------
st.set_page_config(page_title="Reddit Comment Generator", page_icon="💬")
MODEL_NAME = "gemini-1.5-flash"  # swap to "gemini-1.5-pro" if you prefer
MAX_COMMENTS = 25
TIMEOUT = 20

# ---------------- API Key ----------------
API_KEY = os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    st.error("Missing GOOGLE_API_KEY. Add it in Manage app → Settings → Secrets.")
    st.stop()
genai.configure(api_key=API_KEY)

# ---------------- Helpers ----------------import json
import time

@st.cache_data(show_spinner=False, ttl=600)
def fetch_thread(url: str):
    # 1) Normalize URL to old.reddit.com and build .json endpoints
    if not re.match(r"^https?://", url):
        raise ValueError("Enter a full Reddit URL starting with http(s)://")
    base = url.split("?")[0].rstrip("/")
    base = base.replace("https://www.reddit.com", "https://old.reddit.com")
    base = base.replace("https://reddit.com", "https://old.reddit.com")

    json_urls = [
        base + ".json?raw_json=1",  # richer text formatting
        base + ".json",             # fallback
    ]

    # 2) Two realistic browser headers to rotate if blocked
    chrome_headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/122.0 Safari/537.36"),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://old.reddit.com/",
        "Connection": "keep-alive",
        "DNT": "1",
    }
    firefox_headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) "
                       "Gecko/20100101 Firefox/123.0"),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://old.reddit.com/",
        "Connection": "keep-alive",
        "DNT": "1",
    }

    def try_fetch(hdrs):
        last_err = None
        for ju in json_urls:
            try:
                resp = requests.get(ju, headers=hdrs, timeout=TIMEOUT, allow_redirects=True)
                # Reddit sometimes 200s with HTML. Reject non-JSON quickly.
                ct = resp.headers.get("Content-Type", "")
                if "json" not in ct:
                    # Try to parse anyway; if it explodes, we treat as failure.
                    try:
                        data = resp.json()
                    except Exception:
                        last_err = RuntimeError(f"Non-JSON response ({ct}) for {ju}")
                        continue
                else:
                    data = resp.json()

                # Expected structure: [post, comments]
                if not isinstance(data, list) or len(data) < 2:
                    last_err = RuntimeError("Unexpected JSON shape from Reddit")
                    continue

                post = data[0]["data"]["children"][0]["data"]
                comments_root = data[1]["data"]["children"]

                title = post.get("title", "")
                body = post.get("selftext", "")
                permalink = "https://www.reddit.com" + post.get("permalink", "")
                subreddit = post.get("subreddit_name_prefixed", "")
                author = post.get("author", "[deleted]")

                comments = []
                for child in comments_root[:MAX_COMMENTS]:
                    if child.get("kind") != "t1":
                        continue
                    cbody = child["data"].get("body", "")
                    if cbody and cbody != "[deleted]":
                        comments.append(cbody)

                return {
                    "title": title,
                    "body": body,
                    "permalink": permalink,
                    "subreddit": subreddit,
                    "author": author,
                    "comments": comments,
                }
            except requests.HTTPError as e:
                last_err = e
                continue
            except Exception as e:
                last_err = e
                continue
        raise last_err or RuntimeError("Failed to fetch Reddit thread")

    # 3) First try with Chrome UA, then retry with Firefox UA
    try:
        return try_fetch(chrome_headers)
    except Exception:
        time.sleep(0.5)
        return try_fetch(firefox_headers)


# ---------------- UI ----------------
st.title("Reddit Comment Generator")

url = st.text_input("Enter a Reddit post URL")

tone = st.radio(
    "What's the vibe? Choose your comment's tone:",
    ["Neutral", "Informative", "Humorous", "Supportive"],
    index=0,
)

length = st.slider("Target length (words)", 50, 220, 100)

# session state
if "post_summary" not in st.session_state:
    st.session_state.post_summary = ""
if "comments_summary" not in st.session_state:
    st.session_state.comments_summary = ""
if "permalink" not in st.session_state:
    st.session_state.permalink = ""
if "replies" not in st.session_state:
    st.session_state.replies = []

col1, col2 = st.columns([1, 1])
with col1:
    fetch_btn = st.button("Fetch & Summarize")
with col2:
    gen_btn = st.button(
        "Generate Comment",
        disabled=not bool(st.session_state.post_summary),
    )

# Fetch + summarize
if fetch_btn:
    if not url:
        st.warning("Paste a full Reddit post link.")
    else:
        try:
            with st.spinner("Fetching thread..."):
                thread = fetch_thread(url)
            st.session_state.permalink = thread["permalink"]

            model = genai.GenerativeModel(MODEL_NAME)

            with st.spinner("Summarizing post..."):
                st.session_state.post_summary = g_summary_post(
                    model, thread["title"], thread["body"]
                )

            with st.spinner("Summarizing comments..."):
                st.session_state.comments_summary = g_summary_comments(
                    model, thread["comments"]
                )

            st.success("Summaries ready. Now generate a comment.")
            st.session_state.replies = []  # reset previous results
        except requests.HTTPError as http_err:
            st.error(f"HTTP error fetching Reddit: {http_err}")
        except Exception as e:
            st.error(f"Something broke: {e}")

# Show summaries if available
if st.session_state.post_summary:
    with st.expander("Post Summary", expanded=True):
        st.write(st.session_state.post_summary or "No content to summarize.")
    with st.expander("Comments Summary", expanded=True):
        st.write(st.session_state.comments_summary or "No comments to summarize.")

# Generate one or more replies
if gen_btn:
    reply = generate_new_option(
        st.session_state.permalink,
        tone,
        length,
        st.session_state.post_summary,
        st.session_state.comments_summary,
    )
    if reply:
        st.session_state.replies.append(reply)

if st.session_state.replies:
    st.markdown("### Suggested Comments")
    for i, r in enumerate(st.session_state.replies, 1):
        st.markdown(f"**Option {i}:**\n\n{r}\n")
    if st.button("Generate Another"):
        reply = generate_new_option(
            st.session_state.permalink,
            tone,
            length,
            st.session_state.post_summary,
            st.session_state.comments_summary,
        )
        if reply:
            st.session_state.replies.append(reply)
