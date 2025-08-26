import os
import re
import requests
import streamlit as st
import google.generativeai as genai

# ---------------- Config ----------------
st.set_page_config(page_title="Reddit Comment Generator")
MODEL_NAME = "gemini-1.5-flash"  # swap to "gemini-1.5-pro" if needed
MAX_COMMENTS = 25
TIMEOUT = 20

# ---------------- API Key ----------------
API_KEY = os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    st.error("Missing GOOGLE_API_KEY. Add it in Manage app → Settings → Secrets.")
    st.stop()
genai.configure(api_key=API_KEY)

# ---------------- Helpers ----------------
@st.cache_data(show_spinner=False, ttl=600)
def to_json_url(url: str) -> str:
    if not re.match(r"^https?://", url):
        raise ValueError("Enter a full Reddit URL starting with http(s)://")
    base = url.split("?")[0].rstrip("/")
    return base + ".json"

@st.cache_data(show_spinner=False, ttl=600)
def fetch_thread(url: str):
    json_url = to_json_url(url)
    resp = requests.get(
        json_url,
        timeout=TIMEOUT,
        headers={"User-Agent": "streamlit-reddit-commenter/1.0"},
    )
    resp.raise_for_status()
    data = resp.json()
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
        body_c = child["data"].get("body", "")
        if body_c and body_c != "[deleted]":
            comments.append(body_c)

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
        "Summarize the Reddit post for someone who hasn't seen it.\n"
        "Neutral, 3–5 sentences, keep it tight.\n\n"
        f"Title: {title}\n\nBody:\n{body}"
    )
    return (model.generate_content(prompt).text or "").strip()

def g_summary_comments(model, comments):
    text = "\n\n".join(comments) if comments else "No comments."
    prompt = (
        "Summarize the main viewpoints and advice in these Reddit comments.\n"
        "Group similar opinions; output 4–6 concise bullet points.\n\n"
        f"{text}"
    )
    return (model.generate_content(prompt).text or "").strip()

def g_generate_reply(model, url, tone, words, post_summary, comments_summary):
    vibe_instructions = {
        "Neutral": "balanced, straightforward, conversational.",
        "Informative": "explanatory with quick facts or steps, still conversational.",
        "Humorous": "light, dry humor; no snark at the person; no memes or emojis.",
        "Supportive": "empathetic, encouraging, practical next steps.",
    }
    prompt = (
        f"Write a single Reddit-style comment for the thread: {url}\n"
        f"Tone: {tone} ({vibe_instructions.get(tone, 'conversational')}). "
        f"Target length ~{words} words.\n"
        "Rules:\n"
        "- Sound like a normal Reddit user. No marketing, no sales pitch, no corporate voice.\n"
        "- Keep it natural, direct, specific. Avoid clichés and fluff.\n"
        "- If giving advice, include 2–4 concrete, realistic steps.\n"
        "- No emojis, no hashtags, no links, no disclaimers.\n\n"
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
    horizontal=False,
)
length = st.slider("Target length (words)", 50, 220, 100)

# session state to hold summaries and generated options
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
            with st.spinner("Fetching thread..."):
                thread = fetch_thread(url)
            st.session_state.permalink = thread["permalink"]

            model = genai.GenerativeModel(MODEL_NAME)

            with st.spinner("Summarizing post..."):
                st.session_state.post_summary = g_summary_post(model, thread["title"], thread["body"])

            with st.spinner("Summarizing comments..."):
                st.session_state.comments_summary = g_summary_comments(model, thread["comments"])

            st.success("Summaries ready. Now generate a comment.")
            st.session_state.replies = []  # reset previous results
        except requests.HTTPError as http_err:
            st.error(f"HTTP error fetching Reddit: {http_err}")
        except Exception as e:
            st.error(f"Something broke: {e}")

if st.session_state.post_summary:
    with st.expander("Post Summary", expanded=True):
        st.write(st.session_state.post_summary or "No content to summarize.")
    with st.expander("Comments Summary", expanded=True):
        st.write(st.session_state.comments_summary or "No comments to summarize.")

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
    # Generate another fresh option
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
