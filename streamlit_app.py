# streamlit_app.py
import os
import re
import time
import streamlit as st
import requests
import google.generativeai as genai
import praw
from prawcore.exceptions import ResponseException, OAuthException

# ---------------- Config ----------------
st.set_page_config(page_title="Reddit Comment Generator", page_icon="💬")
MODEL_NAME = "gemini-1.5-flash"
MAX_COMMENTS = 25

# ---------------- API Keys ----------------
GEMINI_KEY = os.environ.get("GOOGLE_API_KEY")
if not GEMINI_KEY:
    st.error("Missing GOOGLE_API_KEY. Add it in Manage app → Settings → Secrets.")
    st.stop()
genai.configure(api_key=GEMINI_KEY)

# ---------------- Reddit Auth ----------------
def _init_reddit():
    try:
        reddit = praw.Reddit(
            client_id=os.environ.get("REDDIT_CLIENT_ID"),
            client_secret=os.environ.get("REDDIT_CLIENT_SECRET"),
            user_agent=os.environ.get("REDDIT_USER_AGENT", "comment-generator/1.0"),
            check_for_async=False,
        )
        reddit.read_only = True
        # Sanity check to force auth usage
        _ = reddit.subreddit("all").display_name
        return reddit
    except OAuthException as e:
        raise RuntimeError(
            "Reddit OAuth failed. Double-check CLIENT_ID / CLIENT_SECRET / USER_AGENT. "
            "Use the short ID under the app name, not the app name itself."
        ) from e
    except ResponseException as e:
        raise RuntimeError(f"Reddit API refused the request: {e}") from e

# ---------------- Fetch Thread ----------------
@st.cache_data(show_spinner=False, ttl=600)
def fetch_thread(url: str):
    if not re.match(r"^https?://", url or ""):
        raise ValueError("Enter a full Reddit URL starting with http(s)://")

    reddit = _init_reddit()
    submission = reddit.submission(url=url)
    submission.comments.replace_more(limit=0)
    top_level = submission.comments[:MAX_COMMENTS]

    comments = []
    for c in top_level:
        body = getattr(c, "body", "")
        if body and body != "[deleted]":
            comments.append(body)

    return {
        "title": submission.title or "",
        "body": submission.selftext or "",
        "permalink": f"https://www.reddit.com{submission.permalink}",
        "subreddit": f"r/{submission.subreddit.display_name}",
        "author": f"u/{submission.author.name}" if submission.author else "[deleted]",
        "comments": comments,
    }

# ---------------- Gemini Helpers ----------------
def g_summary_post(model, title, body):
    prompt = (
        "Summarize the Reddit post below in 3–5 sentences. Neutral tone.\n\n"
        f"Title: {title}\n\nBody:\n{body}"
    )
    return (model.generate_content(prompt).text or "").strip()

def g_summary_comments(model, comments):
    text = "\n\n".join(comments) if comments else "No comments."
    prompt = (
        "Summarize the main viewpoints and recurring advice in these Reddit comments. "
        "Group similar opinions. Output 4–6 concise bullet points.\n\n"
        f"{text}"
    )
    return (model.generate_content(prompt).text or "").strip()

def g_generate_reply(model, url, tone, words, post_summary, comments_summary):
    vibe = {
        "Neutral": "balanced, conversational",
        "Informative": "explains with 2–4 concrete steps or facts",
        "Humorous": "light humor; no emojis, no memes",
        "Supportive": "empathetic, encouraging, practical",
    }.get(tone, "conversational")

    prompt = (
        f"Write a Reddit-style comment for the thread: {url}\n"
        f"Tone: {tone} ({vibe}). Target length ~{words} words.\n"
        "Guidelines:\n"
        "- Sound like a normal Reddit user; avoid marketing.\n"
        "- Keep it natural, direct, specific.\n"
        "- No emojis, hashtags, links, or disclaimers.\n\n"
        f"POST SUMMARY:\n{post_summary}\n\n"
        f"COMMENT THEMES:\n{comments_summary}\n\n"
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

# Session state
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
    gen_btn = st.button("Generate Comment", disabled=not bool(st.session_state.post_summary))

if fetch_btn:
    if not url:
        st.warning("Paste a full Reddit post link.")
    else:
        try:
            with st.spinner("Fetching thread via Reddit API..."):
                thread = fetch_thread(url)
            st.session_state.permalink = thread["permalink"]

            model = genai.GenerativeModel(MODEL_NAME)
            st.session_state.post_summary = g_summary_post(model, thread["title"], thread["body"])
            st.session_state.comments_summary = g_summary_comments(model, thread["comments"])

            st.success("Summaries ready. Now generate a comment.")
            st.session_state.replies = []
        except Exception as e:
            st.error(f"Error fetching Reddit: {e}")

if st.session_state.post_summary:
    with st.expander("Post Summary", expanded=True):
        st.write(st.session_state.post_summary)
    with st.expander("Comments Summary", expanded=True):
        st.write(st.session_state.comments_summary)

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
