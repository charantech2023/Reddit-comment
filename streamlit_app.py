import streamlit as st

st.title("Reddit Comment Generator")

topic = st.text_input("Topic")
tone = st.selectbox("Tone", ["Helpful", "Sarcastic", "Supportive", "Critical"])
length = st.slider("Length (words)", 30, 200, 80)

if st.button("Generate"):
    if not topic:
        st.warning("Type a topic first.")
    else:
        # toy generator: swaps in a tone and topic
        templates = {
            "Helpful": "Here’s a quick take on {t}: {t} matters because people overlook the basics. Start small, share sources, and don’t overhype.",
            "Sarcastic": "Hot take on {t}: everyone’s reinventing the wheel, except this wheel is square and somehow trending.",
            "Supportive": "{t} is hard to navigate. Share what you tried, be kind in replies, and remember not everyone has the same context.",
            "Critical": "On {t}: the claims don’t hold up without sources. Show data or it’s just vibes. Happy to change my mind with evidence."
        }
        base = templates[tone].format(t=topic)
        # pad to target length
        while len(base.split()) < length:
            base += " " + base.split()[len(base.split()) % max(1, len(base.split()))]
        st.markdown(base[:len(base.split())*5])  # crude cap
