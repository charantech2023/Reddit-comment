import os
import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="Reddit Comment Generator")
st.title("Reddit Comment Generator")

# 1) Configure Gemini with your key from Streamlit secrets
API_KEY = os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    st.error("Missing GOOGLE_API_KEY. Add it in Streamlit → Manage app → Settings → Secrets.")
    st.stop()
genai.configure(api_key=API_KEY)

# 2) Simple UI
topic = st.text_input("Topic")
tone = st.selectbox("Tone", ["Neutral", "Helpful", "Sarcastic", "Supportive", "Critical"])
length = st.slider("Target length (words)", 40, 220, 90)

# 3) Generate on click
if st.button("Generate"):
    if not topic:
        st.warning("Type a topic first.")
    else:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            f"Write a Reddit-style comment about '{topic}' in a {tone} voice. "
            f"Target ~{length} words. No emojis, no hashtags, no disclaimers."
        )
        try:
            resp = model.generate_content(prompt)
            text = (resp.text or "").strip()
            if not text:
                st.error("Empty response. Try again or tweak inputs.")
            else:
                st.markdown(text)
        except Exception as e:
            st.error(f"Generation failed: {e}")
