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

# ---------------- Helpers ----------------
def _normalize_to_old_reddit(url: str) -> str:
    base = url.split("?")[0].rstrip("/")
    base = base.replace("https://www.reddit.com", "https://old.reddit.com")
    base = base.replace("https://reddit.com", "https://old.reddit.com")
    return base

@st.cache_data(show_spinner=False, ttl=600)
def fetch_thread(url: str):
    # Normalize URL and call the .json endpoint with a browser-like User-Agent
    if not re.match(r"^https?://", url):
        raise ValueError("Enter a full Reddit URL starting with http(s)://")

    base = _normalize_to_old_reddit(url)
    json_url = base + ".json"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0 Safari/537.36"
        )
    }

    resp = requests.get(json_url, timeout=TIMEOUT, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    # data[0] -> post; data[1] -> comments
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

def g_summary_post(model, title, body):
    prompt = (
        "Summarize the Reddit post below for someone who hasn't seen it. "
        "Be neutral, concrete, and brief (3–5 sentences).\n\n"
        f"Title: {title}\n\nBody:\n{body}"
    )
    return (model.generate_content(prompt).text or "").strip()

def g_summary_comments(model, comments):
    text = "\n\n".join(comments) if comments else "No comments."
    prompt = (
        "Summarize the main viewpoints and recurring advice from these Reddit comments. "
        "Group similar opinions. Output 4–6 short bullet points.\n\n"
        f"{text}"
    )
    return (model.generate_content(prompt).text or "").strip()

def g_generate_reply(model, url, tone, words, post_summary, comments_summary):
    vibe = {
        "Neutral": "balanced, straightforward, conversational",
        "Informative": "explanatory with quick facts or steps, still conversational",
        "Humorous": "light, dry humor; no memes; no mocking the OP",
        "Supportive": "empathetic, encouraging, practical next steps",
    }.get(tone, "conversational")

    prompt = (
        f"Write a single Reddit-style comment for the thread: {url}\n"
        f"Tone: {tone} ({vibe}). Target length ~{words} words.\n"
        "Rules:\n"
        "- Sound like a normal Reddit user. No marketing or salesy tone.\n"
        "- Keep it natural, direct, and specific. Avoid clichés and fluff.\n"
        "- If giving advice, include 2–4 concrete, realistic steps.\n"
        "- No emojis, no hashtags, no links, no disclaimers.\n\n"
        f"POST SUMMARY:\n{post_summary}\n\n"
        f"TOP COMMENT THEMES:\n{comments_summary}\n\n"
        "Now draft the reply."
    )
    return (model.generate_content(prompt).text or "").strip()

def generate_new_option(permalink, tone, words, post_summary, comments_summary):
    model = genai.GenerativeModel(MODEL_NAME)
    return g_generate_reply(model, permalink, tone, words, post_summary, comments_summary)

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
