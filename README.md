# Knowledge Quest 🎮

**Knowledge Quest** is a gamified AI-powered learning application built using Python and Streamlit. It helps students turn study material into interactive learning missions, practise questions, track progress, and earn rewards.

> **Project Status:** Active Development

## ✨ Features

- **Student Authentication:** Registration, email OTP verification, login, password reset and logout.
- **Persistent Login:** Restore authenticated sessions after browser refresh.
- **Gamified Learning:** Earn XP and coins, track streaks and progress.
- **AI PDF Quests:** Upload PDFs and generate practice questions using Groq AI.
- **Practice and Revision:** Answer questions, review performance and revisit learning material.
- **Mock Tests:** Complete assessments and review results.
- **Adaptive Learning:** Practise through adaptive question flows.
- **Daily Challenges:** Complete daily learning missions.
- **Arena and Leaderboard:** Compare progress with other accounts sharing the application database.
- **Learning Analytics:** Monitor performance and learning activity.

## 🛠️ Technology Stack

- Python
- Streamlit
- SQLite
- Groq API
- PyMuPDF
- Extra Streamlit Components

## 📁 Project Structure

```text
game4/
│
├── app.py
├── auth.py
├── ui.py
├── data/
│   └── ai_quest.db
├── .streamlit/
│   └── secrets.toml
├── requirements.txt
├── .gitignore
└── README.md
```

## 💻 Installation and Setup

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd game4
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

Alternatively, install the application dependencies:

```powershell
pip install streamlit requests pymupdf extra-streamlit-components
```

### 4. Configure Groq API

Create:

```text
.streamlit/secrets.toml
```

Add your API key:

```toml
GROQ_API_KEY = "YOUR_GROQ_API_KEY"
```

Never upload API keys or credentials to GitHub.

### 5. Run the application

```powershell
streamlit run app.py
```

Open the local URL displayed in your terminal, usually:

```text
http://localhost:8501
```

## 🗄️ Database

Knowledge Quest uses SQLite for local account and learning data.

Database location:

```text
data/ai_quest.db
```

The database stores application information such as user accounts, learning attempts, rewards, progress and activity.

**Important:** Back up the database before making major changes or resetting progress. Do not replace the existing database when updating application code.

The Arena leaderboard is local to accounts sharing the same application database. It is not internet-wide multiplayer.

## 🎨 UI Development

The project includes a separate `ui.py` module for the redesigned user interface.

It contains reusable styling and presentation helpers. It will be integrated into `app.py` while preserving existing authentication, database operations and game logic.

## 🚀 Upcoming Improvements

- Complete the redesigned gaming dashboard.
- Improve quiz and results screens.
- Prevent repeated questions across sessions.
- Improve AI-generated question quality.
- Complete end-to-end feature testing.
- Perform final security checks.
- Prepare application deployment.

## 🔐 Security

- Never commit passwords, OTPs or API keys.
- Keep `.streamlit/secrets.toml` private.
- Keep local virtual environments out of version control.
- Back up the SQLite database regularly.

## 📌 Project Status

Knowledge Quest is under active development. Features and UI are being improved and tested before deployment.

## 📄 License

No open-source license has been specified yet. All rights are reserved by the project author unless a license is added.