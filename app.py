# app.py
import streamlit as st
import json
import streamlit as st
from main import app_graph, get_google_calendar_service

# =========================================================
# 📂 Streamlit Session State
# =========================================================
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "graph_state" not in st.session_state:
    st.session_state["graph_state"] = None
if "in_event_creation" not in st.session_state:
    st.session_state["in_event_creation"] = False
if "show_google_connected_msg" not in st.session_state:
    st.session_state["show_google_connected_msg"] = True

# =========================================================
# 🎨 Streamlit UI
# =========================================================
st.set_page_config(page_title="Event Manager", page_icon="📅", layout="centered")
st.title("📅 Event Manager")
st.caption("Powered by LangGraph, Azure OpenAI, and Google Calendar")


service, auth_url = get_google_calendar_service()
if service:
    if st.session_state["show_google_connected_msg"]:
        st.success("✅ Connected to Google Calendar")
elif auth_url:
    if auth_url.startswith("http"):
        st.info("⚠️ Google Calendar not authorized. Click the link below to authorize:")
        st.link_button("Authorize Google Calendar", auth_url)
    else:
        st.error(auth_url)
    st.stop()

# =========================================================
# 💬 Chat History
# =========================================================
# Show all prior conversation except any assistant JSON-looking text
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        # Skip LLM JSON-like messages (anything starting with '{' from assistant)
        if msg["role"] == "assistant" and msg["content"].strip().startswith("{"):
            continue
        try:
            st.json(json.loads(msg["content"]))
        except (json.JSONDecodeError, TypeError):
            st.markdown(msg["content"])

# =========================================================
# 🟢 Chat Input
# =========================================================
if prompt := st.chat_input("Type 'create an event' to start..."):
    st.session_state["show_google_connected_msg"] = False
    st.session_state["messages"].append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # Step 1: Initialize or continue the graph state
    if not st.session_state["in_event_creation"]:
        st.session_state["in_event_creation"] = True
        current_state = {"conversation": [], "latest_user_input": prompt}
        st.session_state["graph_state"] = app_graph.invoke(current_state)
    else:
        current_state = st.session_state["graph_state"]
        current_state["latest_user_input"] = prompt
        current_state["conversation"].append({"role": "user", "content": prompt})
        st.session_state["graph_state"] = app_graph.invoke(current_state)

    # Step 2: Get assistant reply
    state = st.session_state["graph_state"]
    reply = state["conversation"][-1]["content"]

    # Step 3: Save and display only natural-language assistant replies (no JSON)
    if not reply.strip().startswith("{"):
        st.session_state["messages"].append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)

# =========================================================
# 🟢 Display Final Event & Calendar Link
# =========================================================
state = st.session_state.get("graph_state")
if state and state.get("finished"):
    final_result = state.get("event_result") or {}
    calendar_link = state.get("calendar_link") or final_result.get("calendar_link")

    with st.chat_message("assistant"):
        # Natural summary before showing final JSON
        st.success("🎉 Event successfully created! Here’s the final event summary:")

        # ✅ Show only one JSON block — the final Google Calendar event
        if final_result:
            st.json(final_result)

        # Display calendar link if available
        if calendar_link:
            st.markdown(f"[📅 View Event in Google Calendar]({calendar_link})")
        else:
            st.warning("No calendar link available. Check if the event was created successfully.")
            st.write("Debug info:", final_result)

    # Reset for next run
    st.session_state["in_event_creation"] = False
    st.session_state["graph_state"] = None