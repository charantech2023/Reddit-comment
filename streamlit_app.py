import os
import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="Reddit Comment Generator")
st.title("Reddit Comment Generator")

API_KEY = os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    st.error("Missing GOOGLE_API_KEY in Streamlit secrets.")
    st.stop()
genai.configure(api_key=API_KEY)

topic = st.text_input("Topic")
tone = st.selectbox("Tone", ["Neutral", "Helpful", "Sarcastic", "Supportive", "Critical"])
length = st.slider("Target length (words)", 40, 220, 90)

if st.button("Generate"):
    if not topic:
        st.warning("Type a topic first.")
    else:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            f"Write a Reddit-style comment about '{topic}' in a {tone} voice. "
            f"Target ~{length} words. No emojis, no hashtags."
        )
        try:
            resp = model.generate_content(prompt)
            st.markdown(resp.text.strip())
        except Exception as e:
            st.error(f"Generation failed: {e}")
