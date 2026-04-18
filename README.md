# Event-Creation-and-Management-AI-Chatbot-
AI-powered event planning assistant with conversational flow, venue recommendations, and Google Calendar integration.

# 📅 AI Event Manager

> AI-powered event planning assistant with conversational flow, venue recommendations, and Google Calendar integration.

---

## 🚀 Features

* 💬 Conversational event creation (LLM-powered)
* 🧠 Asks questions **one at a time**
* 🏢 Venue suggestions for offline events
* 📅 Google Calendar event creation
* ✉️ Sends invites to attendees
* 🔗 Provides calendar event link

---

## 🧩 How It Works

1. User types:

   ```
   create an event
   ```

2. The assistant:

   * Asks questions step-by-step
   * Collects event details one at a time

3. For offline events:

   * Suggests venues
   * User selects a venue by typing its number
   * The selected venue is shown for confirmation
   * **User must type "yes" or "okay" to proceed further**

4. After collecting all details:

   * Event is created in Google Calendar
   * Event link is displayed

---

## 📸 Screenshots

### 💬 Chat Flow



---

### 🏢 Venue Selection


---

### 📅 Event Created


---

## 🛠️ Tech Stack

* **Frontend:** Streamlit
* **Backend:** LangGraph
* **LLM:** Azure OpenAI
* **APIs:**

  * Google Calendar API
  * Tavily API

---

## 📂 Project Structure

```
.
├── app.py
├── main.py
├── requirements.txt
├── README.md
├── .gitignore
└── assets/
```

---

## ⚙️ Setup

1. Clone repo:

   ```
   git clone https://github.com/your-username/your-repo-name.git
   ```

2. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

3. Create `.env` file and add:

   ```
   AZURE_OPENAI_ENDPOINT=
   AZURE_OPENAI_API_KEY=
   AZURE_OPENAI_DEPLOYMENT=
   AZURE_OPENAI_API_VERSION=
   TAVILY_API_KEY=
   ```

4. Add Google OAuth:

   * Place `client_secret.json` in root

5. Run app:

   ```
   streamlit run app.py
   ```

---

## 🔐 Notes

* `.env`, `client_secret.json`, and `token.json` are not included for security reasons
* Venue addresses may not always be accurate due to API limitations

---

## 📜 License

MIT License

