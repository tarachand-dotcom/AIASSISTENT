# Intelligent Personal AI Assistant

An AI-powered personal assistant built with **Python**, **Streamlit**, and **Llama 3 via Ollama**.  
The application provides a chat-based experience to manage tasks, summarize emails, schedule events, and store data persistently using SQLite.

---

## Description

**Intelligent Personal AI Assistant** is a modular assistant application designed to improve daily productivity through natural language interaction.  
It uses an LLM to detect user intent and return structured JSON outputs, enabling seamless automation for tasks and scheduling while keeping the interface simple and user-friendly.

---

## Features

- Chat-based AI assistant interface (Streamlit)
- Intent detection with structured JSON outputs
- Task creation, completion, and deletion
- Event creation and event listing
- Email understanding workflow (summary, action extraction, priority)
- Voice input/output module support
- Persistent local data storage with SQLite
- Error handling and safe fallbacks for LLM/API failures

---

## Tech Stack

- **Python**
- **Streamlit**
- **Ollama** (Llama 3 model)
- **SQLite**

---

## Project Structure

```text
Intelligent-Personal-AI-Assistant/
├── app.py              # Main Streamlit frontend and UI logic
├── llm.py              # Ollama LLM integration
├── prompt.py           # System prompt for intent + structured output
├── task_manager.py     # SQLite database operations (tasks/events)
├── utils.py            # JSON parsing and helper utilities
├── gmail_api.py        # Gmail API integration
├── calendar_api.py     # Google Calendar API integration
├── voice.py            # Speech-to-text and text-to-speech utilities
├── requirements.txt    # Project dependencies
└── README.md           # Project documentation
```

---

## Installation Steps

### 1) Clone the repository

```bash
git clone <your-repo-url>
cd <your-repo-folder>
```

### 2) (Optional but recommended) Create and activate a virtual environment

```bash
python -m venv .venv
```

**Windows (PowerShell):**
```bash
.venv\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Set up Ollama and model

```bash
ollama pull llama3
ollama serve
```

### 5) (Optional) Google integrations setup

If using Gmail/Calendar features:
- Enable Gmail API and Google Calendar API in Google Cloud Console
- Download `credentials.json`
- Place `credentials.json` in the project root

---

## How to Run

Start the Streamlit app:

```bash
streamlit run app.py
```

Open the local URL shown in terminal (usually `http://localhost:8501`).

---

## Screenshots

> Placeholder: Add application screenshots here.

- `screenshots/chat-ui.png` — Chat interface
- `screenshots/tasks-panel.png` — Task management section
- `screenshots/events-panel.png` — Event scheduling display
- `screenshots/sidebar-controls.png` — Sidebar controls

---

## Future Improvements

- User authentication and multi-user support
- Better conversation memory and context retention
- Richer calendar conflict resolution and suggestions
- Notification/reminder support (desktop/email)
- Deployable cloud version with secure secret management
- Automated tests and CI/CD pipeline

---

## Author

**Your Name**  
GitHub: [your-github-profile](https://github.com/your-github-profile)

"# AIASSISTENT" 
