# main.py
import os
import json
import re
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import AzureOpenAI
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph, END
import streamlit as st

# =========================================================
# 🔑 Load environment variables & Initialize Client
# =========================================================
load_dotenv()
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
)

# =========================================================
# 🛠️ Google Calendar OAuth & Service
# =========================================================
SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_FILE = "token.json"


def get_google_calendar_service():
    creds = None
    auth_url = None

    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"⚠️ Error loading credentials from token.json: {e}")

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
            print("✅ Token refreshed successfully.")
        except Exception as e:
            print(f"⚠️ Token refresh failed: {e}")
            creds = None

    if creds and creds.valid:
        service = build("calendar", "v3", credentials=creds)
        return service, None

    if os.path.exists("client_secret.json"):
        flow = InstalledAppFlow.from_client_secrets_file(
            "client_secret.json",
            scopes=SCOPES,
            redirect_uri="http://localhost:8080/",  # 🔥 important
        )

   
        creds = flow.run_local_server(port=8080)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

        service = build("calendar", "v3", credentials=creds)
        return service, None
    else:
        return None, "Error: client_secret.json not found."

# =========================================================
# 🛠️ Tavily Venue Search Integration
# =========================================================
def parse_venue_request(user_input: str):
    """Detects various phrases for suggesting venues and extracts the city."""
    pattern = r"suggest.*?venue[s]?.*?(?:in|around)\s+(.+)"
    match = re.search(pattern, user_input, re.IGNORECASE)
    if match:
        city = match.group(1).strip()
        return re.sub(r'[?.!]$', '', city)  # Remove trailing punctuation
    return None

def search_venues(city: str):
    """Call Tavily API to fetch venue suggestions in a city with clean name, address, and link."""
    url = "https://api.tavily.com/search"
    headers = {
        "Authorization": f"Bearer {TAVILY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": f"top banquet halls in {city} with full address, Google Maps link and contact details",
        "search_depth": "advanced",
        "max_results": 5
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()

        venues = []
        for res in data.get("results", []):
            name = res.get("title", "").strip() or "Unknown Venue"
            snippet = res.get("snippet", "").strip()
            url = res.get("url", "").strip()

            # Extract possible address (heuristic: remove extra text, keep 1–2 lines)
            # Try to extract address-like patterns
            address = "Address not available"

            if snippet:
                # Look for common address patterns (numbers, commas, locations)
                match = re.search(r'\d{1,5}.*?,.*?(?:India|USA|UK|Maharashtra|Delhi|Mumbai)', snippet, re.IGNORECASE)
                if match:
                    address = match.group(0)
                else:
                    # fallback: take first 120 chars
                    address = snippet[:120] + "..." if len(snippet) > 120 else snippet
            if len(address) > 120:
                address = address[:120] + "..."

            venues.append({
                "name": name,
                "address": address,
                "link": url if url else "Link not available"
            })

        return venues
    except Exception as e:
        print(f"⚠️ Tavily API error: {e}")
        return []

# =========================================================
# 🛠️ Event creation functions
# =========================================================
def is_valid_email(email):
    return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", email.strip()))

def create_google_online_event(name, description, date, time, attendees=None, link=None, timezone="Asia/Kolkata"):
    service, auth_url = get_google_calendar_service()
    if not service:
        return {"status": "error", "message": "Google Calendar not authorized.", "auth_url": auth_url}, None

    if attendees is None: attendees = []
    attendees = [a.strip() for a in attendees if a and is_valid_email(a)]

    try:
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(hours=1)
    except ValueError as e:
        return {"status": "error", "message": f"Invalid date or time format: {e}"}, None

    event = { "name": name, "description": description, "date": date, "time": time, "attendees": attendees, "link": link }
    g_event = {
        "summary": name,
        "description": f"{description}\n\nMeet link: {link}" if link else description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
        "attendees": [{"email": a} for a in attendees],
    }

    try:
        # ✅ Send email invites to all attendees
        created = service.events().insert(calendarId="primary", body=g_event, sendUpdates="all").execute()
        return {"status": "success", "event": event, "calendar_link": created.get("htmlLink")}, created.get("htmlLink")
    except Exception as e:
        return {"status": "error", "message": str(e)}, None

def create_google_offline_event(name, description, date, time, venue, attendees_count, food, facilities=None, attendies=None, timezone="Asia/Kolkata"):
    service, auth_url = get_google_calendar_service()
    if not service:
        return {"status": "error", "message": "Google Calendar not authorized.", "auth_url": auth_url}, None

    if attendies is None: attendies = []
    attendies = [a.strip() for a in attendies if a and is_valid_email(a)]

    try:
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(hours=1)
    except ValueError as e:
        return {"status": "error", "message": f"Invalid date/time: {e}"}, None

    event = {
        "name": name,
        "description": description,
        "date": date,
        "time": time,
        "venue": venue,
        "facilities": facilities,
        "attendees_count": attendees_count,
        "food": food,
        "attendies": attendies
    }

    location_str = venue["name"] if isinstance(venue, dict) else venue
    desc_str = (
        f"{description}\n\n"
        f"--- Event Details ---\n"
        f"Venue: {venue.get('name', venue)}\n"
        f"Address: {venue.get('address', 'Not available')}\n"
        f"Link: {venue.get('link', 'Not available')}\n"
        f"Facilities: {facilities if facilities else 'Not specified'}\n"
        f"Attendees: {attendees_count}\n"
        f"Food: {food}"
    ) if isinstance(venue, dict) else description

    g_event = {
        "summary": name,
        "location": location_str,
        "description": desc_str,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
        "attendees": [{"email": a} for a in attendies],
    }

    try:
        # ✅ Send email invites to all attendees
        created = service.events().insert(calendarId="primary", body=g_event, sendUpdates="all").execute()
        return {"status": "success", "event": event, "calendar_link": created.get("htmlLink")}, created.get("htmlLink")
    except Exception as e:
        return {"status": "error", "message": str(e)}, None

# =========================================================
# 🧠 LLM Conversational State Machine
# =========================================================
SYSTEM_PROMPT = """
You are a friendly and precise Event Planning Assistant.
Your goal is to collect all the necessary information to create an event in Google Calendar.

🎯 Behavior:
1. Start by **asking whether the user wants to create an "online" or "offline" event**.
2. Ask for ONLY ONE piece of information at a time.
3. Do NOT ask multiple questions in a single message.
4. Wait for the user to respond before asking the next question.
5. Move step-by-step through the required fields in order.
6. When the user provides information, check carefully for missing or invalid details.
7. If information is missing, DO NOT list everything at once.
   Instead, ask ONLY for the next missing field.
   Keep the conversation step-by-step and minimal in a natural conversational tone.
8. Once all required information is complete and valid, respond **only with a single JSON object** — no explanations or extra text.
9.Only include facilities only if explicitly and exactly mentioned by the user. Keep facilities field optional. 
10. Do not include calendar links in your JSON. The system will automatically create the event in Google Calendar and display the link.

🧾 Validation:
- Dates must be in YYYY-MM-DD format.
- Times must be in HH:MM (24-hour) format.
- Email addresses must be valid.
- If the event is offline, the venue may be a string or an object with {"name", "address", "link"}.

📋 Required fields:

For ONLINE events:
- name
- description
- date (YYYY-MM-DD)
- time (HH:MM)
- attendees (emails)
- link (Google Meet or similar URL)

For OFFLINE events:
- name
- description
- date (YYYY-MM-DD)
- time (HH:MM)
- venue (object or string)
- facilities (optional,allow skipping)
- attendees_count (integer)
- food
- attendies (emails)

📦 Final JSON formats:

ONLINE:
{
  "event_type": "online",
  "data": {
    "name": "...",
    "description": "...",
    "date": "...",
    "time": "...",
    "attendees": ["..."],
    "link": "..."
  }
}

OFFLINE:
{
  "event_type": "offline",
  "data": {
    "name": "...",
    "description": "...",
    "date": "...",
    "time": "...",
    "venue": {"name": "...", "address": "...", "link": "..."},
    "facilities": "...",
    "attendees_count": 0,
    "food": "...",
    "attendies": ["..."]
  }
}

💬 Tone:
- Be polite, natural, and clear.
- When asking for missing info, first list what you have, then ask for what's missing. For example:
  - "Great! Here's what I have so far:\n  - **Event Name**: Team Sync\n  - **Date**: 2023-10-28\n\nI just need the event time (HH:MM) to proceed."
  - "Okay, I've got the following:\n  - **Event Name**: Project Kick-off\n  - **Date**: 2023-11-05\n  - **Time**: 14:00\n  - **Venue**: Main Conference Room\n\nCould you please provide the attendee emails and food preferences?"


Final JSON format:
{"event_type": "online", "data": {"name": "...", "description": "...", "date": "...", "time": "...", "attendees": [...], "link": "..."}}
OR
{"event_type": "offline", "data": {"name": "...", "description": "...", "date": "...", "time": "...", "venue": {"name": "...", "address": "...", "link": "..."}, "facilities": "...", "attendees_count": 0, "food": "...", "attendies": [...]} }
"""

class AppState(TypedDict):
    latest_user_input: Optional[str]
    conversation: List[dict]
    event_data: Optional[dict]
    event_result: Optional[dict]
    calendar_link: Optional[str]
    finished: bool
    venue_options: Optional[List[dict]]
    awaiting_city_for_venue: Optional[bool]

def start_event_creation(state: AppState) -> AppState:
    conversation = state.get("conversation", [])
    if not conversation:
        conversation = [{"role": "system", "content": SYSTEM_PROMPT}]
    if state.get("latest_user_input"):
        conversation.append({"role": "user", "content": state["latest_user_input"]})
    state["conversation"] = conversation
    state["finished"] = False
    return state

def collect_event_data(state: AppState) -> AppState:
    latest_user_input = state.get("latest_user_input", "")

    # Step 1: If user previously got venue options and now typed a number
    if state.get("venue_options") and latest_user_input.isdigit():
        choice = int(latest_user_input)
        if 1 <= choice <= len(state["venue_options"]):
            selected_venue = state["venue_options"][choice - 1]
            state["conversation"].append({
                "role": "assistant",
                "content": f"Here is the selected venue: {json.dumps(selected_venue)}"
            })
            state["venue_options"] = None
            return state

    # New: If we previously asked the user for a city to search venues in and they just replied with the city name,
    # treat that reply as the city and run the venue search.
    if state.get("awaiting_city_for_venue") and latest_user_input and latest_user_input.strip():
        city = latest_user_input.strip()
        state["awaiting_city_for_venue"] = False
        venues = search_venues(city)
        if venues:
            state["venue_options"] = venues
            msg = "Here are some venue suggestions:\n\n"
            for idx, v in enumerate(venues, start=1):
                msg += f"{idx}. **{v['name']}**\n   📍 {v['address']}\n   🔗 {v['link']}\n\n"
            msg += "👉 Please type the number of the venue you want."
            state["conversation"].append({"role": "assistant", "content": msg})
            return state
        else:
            state["conversation"].append({
                "role": "assistant",
                "content": f"Sorry, I couldn't find any venues in {city}. Please provide one manually."
            })
            return state

    # Step 2: Check if the user is asking for venue suggestions
    city = parse_venue_request(latest_user_input)
    if city:
        venues = search_venues(city)
        if venues:
            state["venue_options"] = venues
            msg = "Here are some venue suggestions:\n\n"
            for idx, v in enumerate(venues, start=1):
                msg += f"{idx}. **{v['name']}**\n   📍 {v['address']}\n   🔗 {v['link']}\n\n"
            msg += "👉 Please type the number of the venue you want."
            state["conversation"].append({"role": "assistant", "content": msg})
            return state
        else:
            state["conversation"].append({
                "role": "assistant",
                "content": f"Sorry, I couldn't find any venues in {city}. Please provide one manually."
            })
            return state

    # If the user asked to suggest venues but DID NOT mention a city, ask for the city.
    # Detect common phrasings like "suggest a venue", "recommend venues", "find venues", etc.
    if re.search(r"\b(suggest|recommend|find|search|show)\b.*\bvenue[s]?\b", latest_user_input, re.IGNORECASE):
        # Ask the user for the city and set a flag so their next message is used as the city.
        state["conversation"].append({
            "role": "assistant",
            "content": "Sure — which city should I search for venues in?"
        })
        state["awaiting_city_for_venue"] = True
        return state

    # Step 3: Otherwise, continue normal LLM flow
    response = client.chat.completions.create(
        model=DEPLOYMENT_NAME,
        messages=state["conversation"],
        max_tokens=500,
        temperature=0.7,
    )
    llm_reply = response.choices[0].message.content

    state["conversation"].append({"role": "assistant", "content": llm_reply})

    try:
        json_match = re.search(r"\{.*\}", llm_reply, re.DOTALL)
        if json_match:
            data_json = json.loads(json_match.group(0))
            if "event_type" in data_json and "data" in data_json:
                state["event_data"] = data_json
    except json.JSONDecodeError:
        pass

    return state

def finalize_event(state: AppState) -> AppState:
    event_info = state.get("event_data")
    if not event_info:
        state["finished"] = True
        state["event_result"] = {"status": "error", "message": "No event data available"}
        return state

    event_type = event_info["event_type"]
    data = event_info["data"]

    result, calendar_link = None, None
    if event_type == "online":
        result, calendar_link = create_google_online_event(**data)
    elif event_type == "offline":
        result, calendar_link = create_google_offline_event(**data)

    state["event_result"] = result
    state["calendar_link"] = calendar_link
    state["finished"] = True
    return state

# =========================================================
# 🔄 Build Graph
# =========================================================
def should_finalize(state: AppState) -> str:
    if state.get("event_data"):
        return "finalize"
    else:
        return "end"

builder = StateGraph(AppState)
builder.add_node("start", start_event_creation)
builder.add_node("collect", collect_event_data)
builder.add_node("finalize", finalize_event)
builder.set_entry_point("start")
builder.add_edge("start", "collect")
builder.add_conditional_edges(
    "collect",
    should_finalize,
    { "finalize": "finalize", "end": END }
)
builder.add_edge("finalize", END)
app_graph = builder.compile()