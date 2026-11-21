
import streamlit as st
import random
import json
import re
import requests
import pymupdf
import auth
import sqlite3
import hashlib
import difflib
import html
from pathlib import Path
import secrets
import datetime
import json
import extra_streamlit_components as stx

# =====================================================
# QUESTION ANTI-REPETITION STORAGE
# =====================================================
APP_DIR = Path(__file__).resolve().parent
QUEST_DB_PATH = APP_DIR / "data" / "ai_quest.db"
QUEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def init_question_history():
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS question_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, source_hash TEXT NOT NULL,
            question_hash TEXT NOT NULL, question_text TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, source_hash, question_hash)
        )""")

def normalize_question(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()

def question_hash(text):
    return hashlib.sha256(normalize_question(text).encode("utf-8")).hexdigest()

def get_question_history(user_id, source_hash):
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        rows = conn.execute("SELECT question_text FROM question_history WHERE user_id=? AND source_hash=? ORDER BY id DESC", (str(user_id), source_hash)).fetchall()
    return [row[0] for row in rows]

def save_question_history(user_id, source_hash, questions):
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        conn.executemany("INSERT OR IGNORE INTO question_history(user_id,source_hash,question_hash,question_text) VALUES(?,?,?,?)",
            [(str(user_id), source_hash, question_hash(q), q) for q in questions])

def is_duplicate_question(candidate, known_questions, threshold=0.88):
    candidate_norm = normalize_question(candidate)
    if not candidate_norm:
        return True
    for known in known_questions:
        known_norm = normalize_question(known)
        if candidate_norm == known_norm:
            return True
        if min(len(candidate_norm), len(known_norm)) >= 24 and difflib.SequenceMatcher(None, candidate_norm, known_norm).ratio() >= threshold:
            return True
    return False

init_question_history()

# =====================================================
# PERSISTENT PLAYER ATTEMPT ANALYTICS (PHASE 5)
# =====================================================
def init_attempt_analytics():
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS player_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT '',
            difficulty TEXT NOT NULL DEFAULT '',
            question_text TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS mock_test_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            test_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            total_questions INTEGER NOT NULL,
            correct_answers INTEGER NOT NULL,
            score_percent INTEGER NOT NULL,
            duration_seconds INTEGER NOT NULL,
            completed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

def save_player_attempt(user_id, subject, source, difficulty, question_text, is_correct, xp_awarded=0):
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        conn.execute("INSERT INTO player_attempts(user_id,subject,source,difficulty,question_text,is_correct) VALUES(?,?,?,?,?,?)",
            (str(user_id), str(subject), str(source or ''), str(difficulty or ''), str(question_text), int(bool(is_correct))))
    record_daily_learning(user_id, is_correct, int(xp_awarded or 0))

def get_player_attempts(user_id):
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT subject,source,difficulty,question_text,is_correct,created_at FROM player_attempts WHERE user_id=? ORDER BY id DESC", (str(user_id),)).fetchall()
    return [dict(row) for row in rows]


def save_mock_test_summary(user_id, test_name, subject, total, correct, elapsed_seconds):
    score = round((correct / total) * 100) if total else 0
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        conn.execute("INSERT INTO mock_test_history(user_id,test_name,subject,total_questions,correct_answers,score_percent,duration_seconds) VALUES(?,?,?,?,?,?,?)",
            (str(user_id), test_name, subject, int(total), int(correct), int(score), int(elapsed_seconds)))


def get_mock_test_history(user_id):
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT test_name,subject,total_questions,correct_answers,score_percent,duration_seconds,completed_at FROM mock_test_history WHERE user_id=? ORDER BY id DESC", (str(user_id),)).fetchall()
    return [dict(row) for row in rows]

init_attempt_analytics()

# =====================================================
# PHASE 8/9 - ADAPTIVE LEARNING + LOCAL COMPETITION
# =====================================================
def init_phase89_tables():
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS daily_learning_stats (
            user_id TEXT NOT NULL, day TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            correct INTEGER NOT NULL DEFAULT 0, xp_earned INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(user_id, day)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS daily_challenge_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, challenge_day TEXT NOT NULL,
            question_hash TEXT NOT NULL, is_correct INTEGER NOT NULL, submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, challenge_day)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS player_profiles (
            user_id TEXT PRIMARY KEY,
            xp INTEGER NOT NULL DEFAULT 0,
            coins INTEGER NOT NULL DEFAULT 0,
            total_attempts INTEGER NOT NULL DEFAULT 0,
            correct_answers INTEGER NOT NULL DEFAULT 0,
            current_streak INTEGER NOT NULL DEFAULT 0,
            best_streak INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")

def record_daily_learning(user_id, is_correct, xp=0):
    day = __import__('datetime').date.today().isoformat()
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        conn.execute("""INSERT INTO daily_learning_stats(user_id,day,attempts,correct,xp_earned)
            VALUES(?,?,1,?,?) ON CONFLICT(user_id,day) DO UPDATE SET
            attempts=attempts+1, correct=correct+excluded.correct, xp_earned=xp_earned+excluded.xp_earned""",
            (str(user_id), day, int(bool(is_correct)), int(xp)))

def get_daily_learning(user_id):
    day = __import__('datetime').date.today().isoformat()
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        row = conn.execute("SELECT attempts,correct,xp_earned FROM daily_learning_stats WHERE user_id=? AND day=?", (str(user_id), day)).fetchone()
        rows = conn.execute("SELECT day FROM daily_learning_stats WHERE user_id=? AND attempts>0 ORDER BY day DESC", (str(user_id),)).fetchall()
    today = row or (0,0,0)
    dates = [r[0] for r in rows]
    streak = 0
    date_mod = __import__('datetime').date
    check = date_mod.today()
    if dates and dates[0] == check.isoformat():
        pass
    elif dates and dates[0] == (check - __import__('datetime').timedelta(days=1)).isoformat():
        check -= __import__('datetime').timedelta(days=1)
    else:
        check = None
    if check:
        while check.isoformat() in dates:
            streak += 1
            check -= __import__('datetime').timedelta(days=1)
    return {"attempts":today[0], "correct":today[1], "xp":today[2], "streak":streak}

def save_daily_challenge_result(user_id, challenge_day, q_hash, is_correct):
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        conn.execute("INSERT OR IGNORE INTO daily_challenge_history(user_id,challenge_day,question_hash,is_correct) VALUES(?,?,?,?)",
            (str(user_id), challenge_day, q_hash, int(bool(is_correct))))

def get_daily_challenge_result(user_id, challenge_day):
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        return conn.execute("SELECT is_correct FROM daily_challenge_history WHERE user_id=? AND challenge_day=?", (str(user_id), challenge_day)).fetchone()

def get_daily_challenge_leaderboard(challenge_day, limit=20):
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        rows = conn.execute("SELECT user_id,is_correct,submitted_at FROM daily_challenge_history WHERE challenge_day=? ORDER BY is_correct DESC, submitted_at ASC LIMIT ?", (challenge_day, limit)).fetchall()
    return rows

def classify_topic(question_text):
    text = str(question_text).lower()
    groups = {
        "Basics & Syntax": ["keyword", "syntax", "data type", "boolean", "function", "def", "print", "output", "variable", "collection", "len()"],
        "Object-Oriented Concepts": ["object", "class", "inherit", "constructor", "polymorph", "encapsulation", "extends", "overrid"],
        "AI & Machine Learning": ["artificial intelligence", "learning", "labeled", "generative", "model", "training", "dataset"],
        "SQL & Database Concepts": ["sql", "database", "select", "where", "primary key", "foreign key", "query", "table"],
        "Networking": ["network", "protocol", "routing", "dijkstra", "rip", "ospf", "tcp", "ip", "osi", "http"],
        "General Knowledge": ["planet", "ocean", "capital", "earth", "largest"]
    }
    for topic, keywords in groups.items():
        if any(k in text for k in keywords):
            return topic
    return "Other Topics"

init_phase89_tables()

# =====================================================
# PERSISTENT PLAYER PROFILE + SAFE LEGACY MIGRATION
# =====================================================
def _streak_metrics(user_id):
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        dates = [row[0] for row in conn.execute(
            "SELECT day FROM daily_learning_stats WHERE user_id=? AND attempts>0 ORDER BY day DESC",
            (str(user_id),)
        ).fetchall()]
    if not dates:
        return 0, 0
    from datetime import date, timedelta
    date_set = set(dates)
    today = date.today()
    start = today if today.isoformat() in date_set else (today - timedelta(days=1) if (today-timedelta(days=1)).isoformat() in date_set else None)
    current = 0
    if start:
        d = start
        while d.isoformat() in date_set:
            current += 1
            d -= timedelta(days=1)
    best = 0
    for date_text in sorted(date_set):
        try:
            d = date.fromisoformat(date_text)
        except ValueError:
            continue
        run = 1
        while (d + timedelta(days=run)).isoformat() in date_set:
            run += 1
        best = max(best, run)
    return current, best


def _migrate_legacy_profile(user_id):
    """Create a profile once from saved attempts; legacy reward totals are estimates."""
    uid = str(user_id)
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        existing = conn.execute("SELECT 1 FROM player_profiles WHERE user_id=?", (uid,)).fetchone()
        if existing:
            return
        attempts = conn.execute(
            "SELECT source,difficulty,is_correct,created_at FROM player_attempts WHERE user_id=? ORDER BY id",
            (uid,)
        ).fetchall()
        mock_tests = conn.execute(
            "SELECT COUNT(*) FROM mock_test_history WHERE user_id=?", (uid,)
        ).fetchone()[0]
        # Backfill daily activity from the existing attempt log only where absent.
        aggregates = {}
        for source, difficulty, is_correct, created_at in attempts:
            day = str(created_at or "")[:10]
            if len(day) != 10:
                continue
            item = aggregates.setdefault(day, [0, 0, 0])
            item[0] += 1
            item[1] += int(bool(is_correct))
        for day, values in aggregates.items():
            conn.execute("""INSERT OR IGNORE INTO daily_learning_stats(user_id,day,attempts,correct,xp_earned)
                VALUES(?,?,?,?,?)""", (uid, day, values[0], values[1], 0))
        # Reconstruct best-effort legacy reward totals. Profile persistence is exact from this point forward.
        xp = coins = correct = total = 0
        for source, difficulty, is_correct, _created in attempts:
            total += 1
            right = bool(is_correct)
            correct += int(right)
            if not right:
                continue
            src = str(source or "").lower()
            diff = str(difficulty or "").lower()
            if "mock test" in src:
                xp += 5
            elif "adaptive focus" in src:
                xp += 10; coins += 3
            elif "pdf quest" in src:
                xp += 10; coins += 5
            elif "daily challenge" in src and diff == "challenge":
                xp += 25; coins += 10
            else:
                xp += {"easy":10, "medium":20, "hard":30}.get(diff, 10)
                coins += 5
        xp += int(mock_tests) * 10
        coins += int(mock_tests) * 10
        current_streak, best_streak = _streak_metrics(uid)
        conn.execute("""INSERT INTO player_profiles(user_id,xp,coins,total_attempts,correct_answers,current_streak,best_streak)
            VALUES(?,?,?,?,?,?,?)""", (uid, xp, coins, total, correct, current_streak, best_streak))
        conn.commit()


def load_player_profile(user_id):
    uid = str(user_id)
    _migrate_legacy_profile(uid)
    current_streak, calculated_best = _streak_metrics(uid)
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        attempt_row = conn.execute("SELECT COUNT(*),COALESCE(SUM(is_correct),0) FROM player_attempts WHERE user_id=?", (uid,)).fetchone()
        profile = conn.execute("SELECT xp,coins,best_streak FROM player_profiles WHERE user_id=?", (uid,)).fetchone()
        best_streak = max(int(profile[2] or 0), calculated_best)
        conn.execute("""UPDATE player_profiles SET total_attempts=?,correct_answers=?,current_streak=?,best_streak=?,updated_at=CURRENT_TIMESTAMP
            WHERE user_id=?""", (int(attempt_row[0]), int(attempt_row[1]), current_streak, best_streak, uid))
        conn.commit()
    return {"xp":int(profile[0]), "coins":int(profile[1]), "total_answered":int(attempt_row[0]),
            "correct":int(attempt_row[1]), "streak":current_streak, "best_streak":best_streak,
            "level":int(profile[0]) // 100 + 1}


def persist_player_profile(user_id, xp, coins, best_streak=None):
    uid = str(user_id)
    current_streak, calculated_best = _streak_metrics(uid)
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        total, correct = conn.execute("SELECT COUNT(*),COALESCE(SUM(is_correct),0) FROM player_attempts WHERE user_id=?", (uid,)).fetchone()
        old = conn.execute("SELECT best_streak FROM player_profiles WHERE user_id=?", (uid,)).fetchone()
        best = max(calculated_best, int(old[0] if old else 0), int(best_streak or 0))
        conn.execute("""INSERT INTO player_profiles(user_id,xp,coins,total_attempts,correct_answers,current_streak,best_streak,updated_at)
            VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO UPDATE SET
            xp=excluded.xp,coins=excluded.coins,total_attempts=excluded.total_attempts,correct_answers=excluded.correct_answers,
            current_streak=excluded.current_streak,best_streak=excluded.best_streak,updated_at=CURRENT_TIMESTAMP""",
            (uid,int(xp),int(coins),int(total),int(correct),current_streak,best))
        conn.commit()
    return current_streak, best


# =====================================================
# CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="Knowledge Quest | AI Learning Game",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================
# CUSTOM DESIGN
# =====================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');
:root {
  --bg:#0b1020; --surface:#141b31; --surface-2:#1b2440; --line:rgba(151,165,210,.17);
  --text:#f4f6ff; --muted:#aab4d0; --violet:#8585ff; --violet-2:#a49aff;
  --gold:#ffc247; --mint:#42d9b5; --danger:#ff7586;
}
.stApp {background:radial-gradient(ellipse at 8% -5%,rgba(112,100,255,.20),transparent 34%),radial-gradient(ellipse at 100% 12%,rgba(49,196,174,.09),transparent 28%),var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;}
header[data-testid="stHeader"]{background:transparent}
.block-container{max-width:1440px;padding-top:1.4rem;padding-bottom:3rem;padding-left:clamp(1rem,3vw,2.6rem);padding-right:clamp(1rem,3vw,2.6rem)}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#151d35 0%,#10172a 100%);border-right:1px solid var(--line)}
[data-testid="stSidebar"] *{color:#edf0ff}
[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,h1,h2,h3{font-family:'Space Grotesk',sans-serif;letter-spacing:-.45px;color:var(--text)!important}
p,label,span,div{font-family:'DM Sans',sans-serif}
.hero{position:relative;overflow:hidden;background:linear-gradient(112deg,#242956 0%,#202b50 55%,#16454c 100%);border:1px solid rgba(145,139,255,.34);border-radius:26px;padding:clamp(24px,3.5vw,38px);margin-bottom:22px;box-shadow:0 20px 55px rgba(0,0,0,.22)}
.hero:after{content:'✦';position:absolute;right:5%;top:-22px;font-size:clamp(100px,15vw,175px);line-height:1;color:rgba(255,255,255,.055);transform:rotate(12deg);pointer-events:none}
.hero-tag,.section-label{color:#8fe9dc;font-size:11px;font-weight:800;letter-spacing:1.7px;text-transform:uppercase}
.hero-title{font-family:'Space Grotesk',sans-serif;font-size:clamp(27px,3vw,39px);font-weight:700;margin-top:10px;color:#fff;line-height:1.16;max-width:850px}
.hero-desc{color:#d4dcf4;font-size:15px;margin-top:10px;max-width:720px;line-height:1.65}
.stat-card{height:100%;background:linear-gradient(145deg,rgba(27,37,65,.98),rgba(18,27,48,.98));border:1px solid var(--line);border-radius:19px;padding:19px;min-height:112px;box-shadow:0 9px 25px rgba(0,0,0,.13);transition:transform .2s ease,border-color .2s ease}
.stat-card:hover,.mission-card:hover{transform:translateY(-3px);border-color:rgba(133,133,255,.55)}
.stat-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;font-weight:800}
.stat-value{font-family:'Space Grotesk',sans-serif;font-size:clamp(23px,2.5vw,30px);font-weight:700;color:#fff;margin-top:9px}
.mission-card{height:100%;background:linear-gradient(150deg,rgba(28,39,68,.98),rgba(17,27,48,.98));border:1px solid var(--line);border-radius:20px;padding:22px;min-height:190px;box-shadow:0 10px 24px rgba(0,0,0,.13);transition:transform .2s ease,border-color .2s ease}
.mission-icon{font-size:30px;margin-bottom:12px}.mission-name{font-family:'Space Grotesk',sans-serif;font-size:18px;font-weight:700;color:#f4f6ff}.mission-desc{color:#b4bfd9;font-size:13px;margin-top:8px;line-height:1.6}
.badge{display:inline-block;background:rgba(133,133,255,.13);border:1px solid rgba(133,133,255,.35);color:#d2ceff;padding:5px 10px;border-radius:30px;font-size:10px;font-weight:800;letter-spacing:.8px}
.quest-card,.question-box{background:linear-gradient(145deg,rgba(27,39,67,.98),rgba(17,27,48,.98));border:1px solid var(--line);border-radius:21px;padding:clamp(18px,2.5vw,25px);box-shadow:0 12px 28px rgba(0,0,0,.14)}
.question-box{background:linear-gradient(145deg,#1c2541,#151e35);border-color:rgba(133,133,255,.28)}
.question-text{font-family:'Space Grotesk',sans-serif;font-size:clamp(20px,2.2vw,27px);font-weight:600;color:#f7f8ff;line-height:1.45;margin:18px 0 8px}
.reward-box{background:linear-gradient(135deg,rgba(20,92,76,.28),rgba(17,54,54,.5));border:1px solid rgba(66,217,181,.38);border-radius:19px;padding:21px;color:#baf8e9}
.warning-box{background:linear-gradient(135deg,rgba(111,75,24,.25),rgba(61,43,22,.45));border:1px solid rgba(255,194,71,.35);border-radius:19px;padding:21px;color:#ffe2a7}
/* Consistent controls */
.stTextInput input,.stTextArea textarea,[data-baseweb="select"]>div{background:#151f37!important;color:#f4f6ff!important;border-color:#3b4869!important;border-radius:13px!important}
.stTextInput input:focus,.stTextArea textarea:focus{border-color:var(--violet)!important;box-shadow:0 0 0 1px var(--violet)!important}
[data-testid="stFileUploader"] section{background:rgba(22,32,55,.8);border:1px dashed rgba(133,133,255,.62);border-radius:18px;padding:22px}
[data-testid="stRadio"]>label{color:#dce5f8;font-weight:700}
[data-testid="stRadio"] [role="radiogroup"]{gap:9px}
[data-testid="stRadio"] [role="radio"]{background:rgba(23,34,58,.86);border:1px solid #354563;border-radius:13px;padding:11px 14px;margin-bottom:5px}
[data-testid="stRadio"] [role="radio"]:hover{border-color:var(--violet)}
div.stButton>button,.stFormSubmitButton>button{border-radius:14px;min-height:46px;font-weight:800;border:1px solid #3c4a70;background:#1b2745;color:#edf2ff;transition:all .18s ease}
div.stButton>button:hover,.stFormSubmitButton>button:hover{border-color:var(--mint);background:#223653;color:white;transform:translateY(-1px)}
div.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{background:linear-gradient(100deg,#7775ff,#8a8aff);border:0;color:#11152c;box-shadow:0 8px 20px rgba(104,104,245,.22)}
div.stButton>button[kind="primary"]:hover,.stFormSubmitButton>button[kind="primary"]:hover{filter:brightness(1.08)}
.stProgress>div>div>div>div{background:linear-gradient(90deg,#8585ff,#42d9b5)}
hr{border-color:var(--line)}
[data-testid="stMetric"]{background:rgba(23,34,58,.72);padding:13px;border-radius:15px;border:1px solid var(--line)}
[data-testid="stAlert"]{border-radius:15px}
[data-testid="stTabs"] button{font-weight:700}
footer{visibility:hidden}

/* Phase 4 - results, rewards and revision */
.result-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}
.result-tile{background:rgba(22,32,55,.82);border:1px solid var(--line);border-radius:17px;padding:16px;text-align:center}
.result-number{font-family:'Space Grotesk',sans-serif;font-size:clamp(22px,3vw,32px);font-weight:800;color:#fff}
.result-label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.8px;font-weight:800}
.reward-badge{display:inline-block;border:1px solid rgba(255,194,71,.42);background:rgba(255,194,71,.12);border-radius:30px;padding:8px 13px;color:#ffe09a;font-weight:800;margin:4px}
.revision-card{background:rgba(27,37,65,.78);border:1px solid rgba(255,117,134,.28);border-radius:16px;padding:16px;margin:10px 0}
@media(max-width:700px){.result-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
/* Phase 3 - focused quiz experience */
.quiz-topline{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;color:#aeb9d7;font-size:12px;font-weight:800;letter-spacing:.6px;margin-bottom:10px}
.quiz-panel{background:linear-gradient(145deg,#1d2745,#131c33);border:1px solid rgba(133,133,255,.34);border-radius:23px;padding:clamp(18px,3vw,28px);box-shadow:0 15px 35px rgba(0,0,0,.18)}
.quiz-question{font-family:'Space Grotesk',sans-serif;font-size:clamp(21px,2.3vw,29px);font-weight:700;line-height:1.45;color:#f7f8ff;margin:14px 0 18px}
.quiz-feedback-good{background:linear-gradient(135deg,rgba(20,105,83,.28),rgba(16,52,48,.52));border:1px solid rgba(66,217,181,.5);border-radius:18px;padding:18px 20px}
.quiz-feedback-bad{background:linear-gradient(135deg,rgba(123,50,67,.25),rgba(57,29,46,.52));border:1px solid rgba(255,117,134,.45);border-radius:18px;padding:18px 20px}
.quiz-explanation{background:rgba(27,37,65,.75);border:1px solid var(--line);border-left:4px solid var(--gold);border-radius:15px;padding:17px 19px;margin-top:12px}
.quiz-complete{background:linear-gradient(120deg,#252a59,#1b3c4a);border:1px solid rgba(133,133,255,.38);border-radius:23px;padding:26px;text-align:center}
[data-testid="stRadio"] [role="radiogroup"] label{background:rgba(22,31,53,.9);border:1px solid #354563;border-radius:14px;padding:10px 14px;transition:all .16s ease}
[data-testid="stRadio"] [role="radiogroup"] label:hover{border-color:#8585ff;background:rgba(38,49,80,.95)}
@media(max-width:700px){.quiz-panel{padding:17px;border-radius:18px}.quiz-question{font-size:21px}}

@media(max-width:900px){.block-container{padding-top:1rem}.mission-card{min-height:165px}}
@media(max-width:700px){.block-container{padding-left:.85rem;padding-right:.85rem}.hero{padding:23px 19px;border-radius:20px}.hero:after{font-size:90px;right:2%}.stat-card{min-height:92px;padding:14px;border-radius:16px}.stat-value{font-size:23px}.mission-card{padding:17px;min-height:155px}.question-text{font-size:21px}}
</style>
""", unsafe_allow_html=True)

# =====================================================
# AUTHENTICATION
# =====================================================

auth.initialize_auth_database()

# Persistent browser login: a random token is stored in the browser cookie;
# only its SHA-256 hash is stored in SQLite. Never store passwords in cookies.
PERSISTENT_LOGIN_COOKIE = "knowledge_quest_session"
PERSISTENT_LOGIN_DAYS = 30

def init_persistent_sessions():
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS persistent_login_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            user_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_persistent_sessions_user ON persistent_login_sessions(user_id)")


def _hash_session_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_persistent_login(user):
    token = secrets.token_urlsafe(48)
    token_hash = _hash_session_token(token)
    expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=PERSISTENT_LOGIN_DAYS)).isoformat()
    user_json = json.dumps(user, ensure_ascii=False)
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        conn.execute("INSERT INTO persistent_login_sessions(token_hash,user_id,user_json,expires_at) VALUES(?,?,?,?)",
                     (token_hash, str(user.get("user_id")), user_json, expires))
    return token


def restore_persistent_login(token):
    if not token or not isinstance(token, str):
        return None
    token_hash = _hash_session_token(token)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        row = conn.execute("SELECT user_json,expires_at,revoked FROM persistent_login_sessions WHERE token_hash=?",
                           (token_hash,)).fetchone()
    if not row or row[2]:
        return None
    try:
        expires = datetime.datetime.fromisoformat(row[1])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=datetime.timezone.utc)
        if expires <= datetime.datetime.now(datetime.timezone.utc):
            revoke_persistent_login(token)
            return None
        user = json.loads(row[0])
        if not isinstance(user, dict) or not user.get("user_id"):
            return None
        return user
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def revoke_persistent_login(token):
    if token:
        with sqlite3.connect(QUEST_DB_PATH) as conn:
            conn.execute("UPDATE persistent_login_sessions SET revoked=1 WHERE token_hash=?",
                         (_hash_session_token(token),))


def get_cookie_manager():
    # Keep the component instance per Streamlit session to avoid cross-user state.
    if "_persistent_cookie_manager" not in st.session_state:
        st.session_state["_persistent_cookie_manager"] = stx.CookieManager(key="knowledge_quest_cookie_init")
    return st.session_state["_persistent_cookie_manager"]

init_persistent_sessions()

if "authenticated_user" not in st.session_state:
    st.session_state.authenticated_user = None
if "auth_pending_email" not in st.session_state:
    st.session_state.auth_pending_email = ""
if "auth_development_otp" not in st.session_state:
    st.session_state.auth_development_otp = ""
if "auth_message" not in st.session_state:
    st.session_state.auth_message = ""
if "reset_pending_email" not in st.session_state:
    st.session_state.reset_pending_email = ""
if "reset_development_otp" not in st.session_state:
    st.session_state.reset_development_otp = ""

# Restore authenticated account after refresh/new tab/browser restart.
# Read cookies from the incoming HTTP request first (supported by modern Streamlit),
# then fall back to the CookieManager component for older Streamlit versions.
_cookie_manager = get_cookie_manager()
_cookie_token = None
try:
    _request_cookies = st.context.cookies
    _cookie_token = _request_cookies.get(PERSISTENT_LOGIN_COOKIE)
except Exception:
    _request_cookies = {}

if not _cookie_token:
    try:
        _cookie_data = _cookie_manager.get_all(key="knowledge_quest_cookie_read") or {}
        if isinstance(_cookie_data, dict):
            _cookie_token = _cookie_data.get(PERSISTENT_LOGIN_COOKIE)
    except Exception:
        _cookie_data = {}

if not _cookie_token:
    try:
        _cookie_token = _cookie_manager.get(PERSISTENT_LOGIN_COOKIE)
    except Exception:
        _cookie_token = None

if st.session_state.authenticated_user is None and _cookie_token:
    _restored_user = restore_persistent_login(_cookie_token)
    if _restored_user:
        st.session_state.authenticated_user = _restored_user
        st.session_state["_active_persistent_token"] = _cookie_token
elif st.session_state.authenticated_user is not None:
    st.session_state.setdefault("_active_persistent_token", _cookie_token)


def show_authentication_page():
    st.markdown("""
    <div class="hero">
        <div class="hero-tag">YOUR LEARNING ADVENTURE STARTS HERE</div>
        <div class="hero-title">⚔️ Knowledge Quest</div>
        <div class="hero-desc">Create your student account or log in to continue your learning adventure.</div>
    </div>
    """, unsafe_allow_html=True)

    login_tab, register_tab, reset_tab = st.tabs(["🔐 Login", "✨ Create account", "🔑 Forgot password"])

    with login_tab:
        st.subheader("Welcome back, Explorer!")
        with st.form("login_form"):
            login_email = st.text_input("Email address", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            login_submit = st.form_submit_button("Login", type="primary", use_container_width=True)
        if login_submit:
            ok, message, user = auth.login_user(login_email.strip(), login_password)
            if ok:
                st.session_state.authenticated_user = user
                st.session_state.auth_message = ""
                _new_persistent_token = create_persistent_login(user)
                st.session_state["_active_persistent_token"] = _new_persistent_token
                try:
                    _release_mode_cookie = bool(st.secrets.get("RELEASE_MODE", False))
                except Exception:
                    _release_mode_cookie = False
                _cookie_manager.set(
                    PERSISTENT_LOGIN_COOKIE, _new_persistent_token,
                    key="knowledge_quest_cookie_set_login",
                    max_age=PERSISTENT_LOGIN_DAYS * 24 * 60 * 60,
                    path="/", secure=_release_mode_cookie, same_site="lax"
                )
                # Do not force an immediate rerun here: CookieManager must send its
                # set-cookie command to the browser. Continue into the authenticated app.
            else:
                st.error(message)
        if st.session_state.auth_message:
            st.info(st.session_state.auth_message)

    with register_tab:
        st.subheader("Create your free student account")
        with st.form("register_form"):
            full_name = st.text_input("Full name", key="register_full_name")
            register_email = st.text_input("Email address", key="register_email")
            register_password = st.text_input("Create password", type="password", key="register_password")
            confirm_password = st.text_input("Confirm password", type="password", key="confirm_register_password")
            register_submit = st.form_submit_button("Create account", type="primary", use_container_width=True)
        if register_submit:
            if register_password != confirm_password:
                st.error("The passwords do not match.")
            else:
                ok, message, otp = auth.create_account(full_name.strip(), register_email.strip(), register_password)
                if ok:
                    st.session_state.auth_pending_email = register_email.strip()
                    st.session_state.auth_development_otp = str(otp)
                    st.success(message)
                else:
                    st.error(message)
        if st.session_state.auth_pending_email:
            try:
                release_mode_auth = bool(st.secrets.get("RELEASE_MODE", False))
            except Exception:
                release_mode_auth = False
            if release_mode_auth:
                st.info("Your verification code has been requested. Configure an email/SMS provider to deliver it before enabling release mode.")
            else:
                st.info("Development OTP (local testing only): " + st.session_state.auth_development_otp +
                        " — valid for 5 minutes. It is displayed here instead of being emailed.")
            st.markdown("### 📩 Verify your email")
            st.caption(f"Account: {st.session_state.auth_pending_email}")
            with st.form("otp_form"):
                entered_otp = st.text_input("Enter 6-digit OTP", max_chars=6)
                otp_submit = st.form_submit_button("Verify OTP", type="primary", use_container_width=True)
            if otp_submit:
                verified, verify_message = auth.verify_otp(st.session_state.auth_pending_email, entered_otp.strip())
                if verified:
                    st.success(verify_message)
                    st.session_state.auth_pending_email = ""
                    st.session_state.auth_development_otp = ""
                    st.session_state.auth_message = "Account verified. Please log in using your email and password."
                    st.rerun()
                else:
                    st.error(verify_message)

    with reset_tab:
        st.subheader("Recover your account")
        st.caption("A reset OTP will be shown here for local development. It is not sent by email.")
        with st.form("request_reset_otp_form"):
            reset_email = st.text_input("Registered email address", key="reset_email")
            request_otp = st.form_submit_button("Generate reset OTP", use_container_width=True)
        if request_otp:
            ok, message, otp = auth.request_password_reset(reset_email.strip())
            if ok:
                st.session_state.reset_pending_email = reset_email.strip()
                st.session_state.reset_development_otp = str(otp)
                st.success(message)
            else:
                st.error(message)
        if st.session_state.reset_pending_email:
            try:
                release_mode_reset = bool(st.secrets.get("RELEASE_MODE", False))
            except Exception:
                release_mode_reset = False
            if release_mode_reset:
                st.info("A password reset code was requested. Configure a delivery provider before enabling release mode.")
            else:
                st.info("Your development reset OTP: " + st.session_state.reset_development_otp + " — valid for 5 minutes.")
            with st.form("complete_password_reset_form"):
                reset_otp = st.text_input("Enter 6-digit reset OTP", max_chars=6)
                new_password = st.text_input("New password (minimum 8 characters)", type="password")
                confirm_new_password = st.text_input("Confirm new password", type="password")
                reset_submit = st.form_submit_button("Reset password", type="primary", use_container_width=True)
            if reset_submit:
                if new_password != confirm_new_password:
                    st.error("The new passwords do not match.")
                else:
                    ok, message = auth.reset_password_with_otp(
                        st.session_state.reset_pending_email, reset_otp.strip(), new_password
                    )
                    if ok:
                        st.success(message)
                        st.session_state.reset_pending_email = ""
                        st.session_state.reset_development_otp = ""
                        st.session_state.auth_message = "Password reset successful. Please log in with your new password."
                    else:
                        st.error(message)

    st.markdown("---")
    st.caption("Your account is stored locally in the AI Quest SQLite database. Never share your password or OTP.")


if st.session_state.authenticated_user is None:
    show_authentication_page()
    st.stop()

# The signed-in account supplies the player name; users cannot impersonate another player here.
player_name = st.session_state.authenticated_user["full_name"]

# =====================================================
# QUESTION DATABASE
# =====================================================

questions = {
    "Python Programming": [
        {
            "q": "Which data type stores True or False?",
            "options": ["String", "Boolean", "Integer", "List"],
            "answer": "Boolean",
            "hint": "It represents two logical values.",
            "explanation": "Boolean data stores either True or False."
        },
        {
            "q": "Which keyword is used to define a function?",
            "options": ["function", "define", "def", "fun"],
            "answer": "def",
            "hint": "It is a short, three-letter keyword.",
            "explanation": "Python uses def to define a function."
        },
        {
            "q": "What is the output of print(3 ** 2)?",
            "options": ["6", "9", "8", "32"],
            "answer": "9",
            "hint": "The double star represents exponentiation.",
            "explanation": "3 ** 2 means 3 raised to the power of 2."
        },
        {
            "q": "Which collection is ordered and changeable?",
            "options": ["Tuple", "Set", "List", "String"],
            "answer": "List",
            "hint": "It uses square brackets.",
            "explanation": "Lists are ordered and mutable collections."
        },
        {
            "q": "What does len() return?",
            "options": [
                "Memory address",
                "Length",
                "Data type",
                "Last element"
            ],
            "answer": "Length",
            "hint": "It counts the number of elements.",
            "explanation": "len() returns the number of items in a collection."
        }
    ],

    "Java Programming": [
        {
            "q": "Which keyword creates an object?",
            "options": ["class", "new", "this", "void"],
            "answer": "new",
            "hint": "It is used when calling a constructor.",
            "explanation": "The new keyword allocates an object."
        },
        {
            "q": "What is the entry point of a Java program?",
            "options": ["start()", "run()", "main()", "execute()"],
            "answer": "main()",
            "hint": "It is a special static method.",
            "explanation": "The JVM starts execution from the main method."
        },
        {
            "q": "Java is primarily which type of language?",
            "options": [
                "Markup",
                "Object-oriented",
                "Assembly",
                "Query"
            ],
            "answer": "Object-oriented",
            "hint": "It uses classes and objects.",
            "explanation": "Java supports object-oriented programming."
        },
        {
            "q": "Which keyword inherits a class?",
            "options": ["implements", "extends", "inherits", "super"],
            "answer": "extends",
            "hint": "Used when a child class inherits from a parent.",
            "explanation": "Java uses extends for class inheritance."
        }
    ],

    "Artificial Intelligence": [
        {
            "q": "What does AI stand for?",
            "options": [
                "Automated Internet",
                "Artificial Intelligence",
                "Advanced Interface",
                "Algorithm Integration"
            ],
            "answer": "Artificial Intelligence",
            "hint": "It enables machines to perform intelligent tasks.",
            "explanation": "AI means Artificial Intelligence."
        },
        {
            "q": "Which learning uses labeled data?",
            "options": [
                "Unsupervised",
                "Supervised",
                "Reinforcement",
                "Random"
            ],
            "answer": "Supervised",
            "hint": "The dataset contains correct target outputs.",
            "explanation": "Supervised learning trains on labeled examples."
        },
        {
            "q": "Which is a Generative AI application?",
            "options": [
                "Calculator",
                "ChatGPT",
                "File compression",
                "Basic sorting"
            ],
            "answer": "ChatGPT",
            "hint": "It can generate text.",
            "explanation": "ChatGPT generates responses using a language model."
        }
    ],

    "SQL & Databases": [
        {
            "q": "Which SQL command retrieves data?",
            "options": ["INSERT", "UPDATE", "SELECT", "DELETE"],
            "answer": "SELECT",
            "hint": "It is used to display records.",
            "explanation": "SELECT retrieves data from database tables."
        },
        {
            "q": "Which clause filters rows?",
            "options": ["ORDER BY", "WHERE", "GROUP BY", "JOIN"],
            "answer": "WHERE",
            "hint": "It specifies a condition.",
            "explanation": "WHERE filters records based on a condition."
        },
        {
            "q": "Which key uniquely identifies a row?",
            "options": [
                "Foreign Key",
                "Duplicate Key",
                "Primary Key",
                "Common Key"
            ],
            "answer": "Primary Key",
            "hint": "Its value must uniquely identify the record.",
            "explanation": "A primary key uniquely identifies each row."
        }
    ],

    "General Knowledge": [
        {
            "q": "Which planet is known as the Red Planet?",
            "options": ["Earth", "Venus", "Mars", "Jupiter"],
            "answer": "Mars",
            "hint": "Its surface contains iron oxide.",
            "explanation": "Mars appears reddish due to iron oxide."
        },
        {
            "q": "What is the capital of Japan?",
            "options": ["Seoul", "Tokyo", "Beijing", "Bangkok"],
            "answer": "Tokyo",
            "hint": "It is one of the largest metropolitan cities.",
            "explanation": "Tokyo is the capital of Japan."
        },
        {
            "q": "Which is the largest ocean?",
            "options": [
                "Atlantic",
                "Indian",
                "Arctic",
                "Pacific"
            ],
            "answer": "Pacific",
            "hint": "It covers the largest area.",
            "explanation": "The Pacific Ocean is the largest ocean on Earth."
        }
    ]
}

# =====================================================
# SESSION STATE
# =====================================================

defaults = {
    "xp": 0,
    "coins": 0,
    "level": 1,
    "answered": False,
    "feedback": None,
    "question": None,
    "subject": "Python Programming",
    "difficulty": "Easy",
    "total_answered": 0,
    "correct": 0,
    "streak": 0,
    "best_streak": 0,
    "hint_used": False,
    "generated_questions": [],
    "generated_index": 0,
    "generated_answered": False,
    "generated_feedback": None,
    "generated_hint_used": False,
    "generated_pdf_name": "",
    "generated_correct_count": 0,
    "generated_total_xp": 0,
    "generated_missed_questions": [],
    "generated_bonus_awarded": False,
    "generated_completed": False,
    "generated_user_answers": [],
    "mock_test_active": False,
    "mock_test_completed": False,
    "mock_test_questions": [],
    "mock_test_answers": {},
    "mock_test_review": [],
    "mock_test_index": 0,
    "mock_test_started_at": 0,
    "mock_test_duration_seconds": 0,
    "mock_test_id": 0,
    "mock_test_result_saved": False,
    "mock_test_subject": "Mixed Subjects",
    "mock_test_name": "Placement Practice Test",
    "mock_test_elapsed": 0,
    "daily_challenge_answered": False,
    "daily_challenge_feedback": None,
    "adaptive_practice_questions": [],
    "adaptive_practice_index": 0,
    "adaptive_practice_answers": {},
    "adaptive_practice_started": False,
    "adaptive_practice_feedback": None
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# Always hydrate persisted stats for the active account (including after a relogin).
active_user_id = st.session_state.authenticated_user["user_id"]
loaded_profile = load_player_profile(active_user_id)
for profile_key in ("xp", "coins", "level", "total_answered", "correct", "streak", "best_streak"):
    st.session_state[profile_key] = loaded_profile[profile_key]

# =====================================================
# PLAYER SIDEBAR
# =====================================================

with st.sidebar:

    st.markdown("## ⚔️ KNOWLEDGE QUEST")

    st.markdown("---")

    st.markdown(f"**SIGNED IN AS**  \n{player_name}")
    st.caption(st.session_state.authenticated_user["email"])

    st.markdown(f"""
    <div style="
        background:linear-gradient(135deg,#262b55,#182b46);
        border:1px solid #3b4770;
        padding:20px;
        border-radius:18px;
        text-align:center;
        margin-top:10px;
    ">
        <div style="font-size:46px">🧑‍🚀</div>
        <div style="font-size:19px;font-weight:800">
            {player_name}
        </div>
        <div style="color:#a5b4fc;font-size:12px">
            LEVEL {st.session_state.level} EXPLORER
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### ⚡ Experience")

    current_level_xp = st.session_state.xp % 100

    st.progress(current_level_xp / 100)

    st.caption(
        f"{current_level_xp} / 100 XP to next level"
    )

    st.markdown("---")

    st.markdown("### 🏆 YOUR STATS")

    st.metric("⭐ Total XP", st.session_state.xp)

    st.metric("🪙 Coins", st.session_state.coins)

    st.metric("🔥 Current Streak", st.session_state.streak)

    st.metric("🎯 Correct Answers", st.session_state.correct)

    st.markdown("---")

    if st.button("🔄 Reset Progress", use_container_width=True):
        st.session_state.confirm_reset_progress = True
    if st.session_state.get("confirm_reset_progress", False):
        st.warning("This permanently deletes your saved quiz analytics, mock-test history, daily activity, challenge records, and rewards for this account.")
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button("Yes, delete my progress", type="primary", key="confirm_delete_progress"):
                uid = str(st.session_state.authenticated_user["user_id"])
                with sqlite3.connect(QUEST_DB_PATH) as conn:
                    for table in ("player_attempts", "mock_test_history", "daily_learning_stats", "daily_challenge_history", "question_history", "player_profiles"):
                        conn.execute(f"DELETE FROM {table} WHERE user_id=?", (uid,))
                for key in defaults:
                    st.session_state[key] = defaults[key]
                st.session_state.confirm_reset_progress = False
                st.rerun()
        with cancel_col:
            if st.button("Cancel", key="cancel_delete_progress"):
                st.session_state.confirm_reset_progress = False
                st.rerun()


    st.markdown("---")
    with st.expander("🔑 Change password"):
        with st.form("change_password_form"):
            current_password = st.text_input("Current password", type="password", key="change_current_password")
            new_account_password = st.text_input("New password (minimum 8 characters)", type="password", key="change_new_password")
            confirm_account_password = st.text_input("Confirm new password", type="password", key="change_confirm_password")
            change_password_submit = st.form_submit_button("Update password", use_container_width=True)
        if change_password_submit:
            if new_account_password != confirm_account_password:
                st.error("The new passwords do not match.")
            else:
                changed, change_message = auth.change_password(
                    st.session_state.authenticated_user["user_id"], current_password, new_account_password
                )
                if changed:
                    st.success(change_message)
                else:
                    st.error(change_message)

    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        _logout_token = st.session_state.get("_active_persistent_token") or _cookie_token
        revoke_persistent_login(_logout_token)
        try:
            _cookie_manager.delete(PERSISTENT_LOGIN_COOKIE, key="knowledge_quest_cookie_delete")
        except Exception:
            pass
        st.session_state.pop("_active_persistent_token", None)
        st.session_state.authenticated_user = None
        for profile_key in ("xp", "coins", "level", "total_answered", "correct", "streak", "best_streak"):
            st.session_state[profile_key] = defaults[profile_key]
        st.session_state.auth_pending_email = ""
        st.session_state.auth_development_otp = ""
        st.session_state.reset_pending_email = ""
        st.session_state.reset_development_otp = ""
        st.rerun()

    st.markdown("---")
    st.markdown("### 🧭 NAVIGATION")
    selected_page = st.radio(
        "Go to",
        ["Dashboard", "Create Quest from PDF", "Progress Analytics", "Mock Tests", "Adaptive Learning & Arena"],
        key="navigation_page",
        label_visibility="collapsed"
    )


@st.cache_data(ttl=300, show_spinner=False)
def fetch_groq_chat_models(api_key):
    """Return chat-capable models visible to this Groq API key."""
    response = requests.get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=20
    )
    if not response.ok:
        return [], f"HTTP {response.status_code}: {response.text[:1500]}"

    data = response.json().get("data", [])
    excluded_terms = ("whisper", "orpheus", "prompt-guard", "safeguard")
    model_ids = sorted({
        item.get("id", "") for item in data
        if item.get("id") and not any(term in item.get("id", "").lower() for term in excluded_terms)
    })
    return model_ids, None

if selected_page == "Progress Analytics":
    st.markdown("## 📊 Progress Analytics & Placement Readiness")
    st.caption("Your performance history is saved to your local SQLite database for this account. Tracking begins with this update.")
    user_id = st.session_state.authenticated_user["user_id"]
    attempts = get_player_attempts(user_id)
    total_attempts = len(attempts)
    total_correct = sum(int(a["is_correct"]) for a in attempts)
    overall_accuracy = round((total_correct / total_attempts) * 100) if total_attempts else 0
    subjects = {}
    for attempt in attempts:
        subject_name = attempt["subject"] or "Uncategorized"
        subjects.setdefault(subject_name, {"attempted": 0, "correct": 0})
        subjects[subject_name]["attempted"] += 1
        subjects[subject_name]["correct"] += int(attempt["is_correct"])
    st.markdown("### Your learning overview")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Questions Attempted", total_attempts)
    m2.metric("Correct Answers", total_correct)
    m3.metric("Overall Accuracy", f"{overall_accuracy}%")
    m4.metric("Current XP", st.session_state.xp)
    st.progress(overall_accuracy / 100 if total_attempts else 0)
    if total_attempts == 0:
        st.info("No tracked attempts yet. Complete questions in Dashboard or a PDF Quest; your analytics will appear here.")
    else:
        st.markdown("### Subject performance")
        subject_rows = []
        for subject_name, values in subjects.items():
            acc = round(values["correct"] / values["attempted"] * 100)
            subject_rows.append({"Subject": subject_name, "Attempted": values["attempted"], "Correct": values["correct"], "Accuracy (%)": acc})
        st.dataframe(subject_rows, use_container_width=True, hide_index=True)
        chart_rows = [{"Subject": row["Subject"], "Accuracy (%)": row["Accuracy (%)"]} for row in subject_rows]
        st.bar_chart(chart_rows, x="Subject", y="Accuracy (%)")
        st.markdown("### 🎯 Placement readiness snapshot")
        if overall_accuracy >= 85 and total_attempts >= 20:
            readiness = "Strong practice performance"
            advice = "Keep this consistency and begin timed mock tests and mixed-topic revision."
        elif overall_accuracy >= 70 and total_attempts >= 10:
            readiness = "Developing confidence"
            advice = "Practice more questions in weaker subjects and gradually add timed sessions."
        elif total_attempts >= 5:
            readiness = "Building foundations"
            advice = "Continue regular practice; focus on understanding explanations and revisiting missed questions."
        else:
            readiness = "Just getting started"
            advice = "Complete more practice questions to build a meaningful performance trend."
        st.markdown(f"**Readiness: {readiness}**")
        st.info(advice)
        st.markdown("### Recent activity")
        recent_rows = [{"Subject": a["subject"], "Question": a["question_text"], "Result": "Correct" if a["is_correct"] else "Incorrect", "Date": a["created_at"]} for a in attempts[:15]]
        st.dataframe(recent_rows, use_container_width=True, hide_index=True)
        mock_history = get_mock_test_history(user_id)
        if mock_history:
            st.markdown("### 📝 Mock test history")
            st.dataframe([{"Test": h["test_name"], "Subject": h["subject"], "Score": f"{h['correct_answers']}/{h['total_questions']}", "Accuracy": f"{h['score_percent']}%", "Time (sec)": h["duration_seconds"], "Completed": h["completed_at"]} for h in mock_history[:20]], use_container_width=True, hide_index=True)
        if st.button("🗑️ Clear my analytics history", help="This deletes this account's saved question attempt history only."):
            with sqlite3.connect(QUEST_DB_PATH) as conn:
                conn.execute("DELETE FROM player_attempts WHERE user_id=?", (str(user_id),))
                conn.execute("DELETE FROM mock_test_history WHERE user_id=?", (str(user_id),))
            st.success("Analytics and mock test history cleared.")
            st.rerun()

if selected_page == "Dashboard":
    # =====================================================
    # MAIN DASHBOARD
    # =====================================================

    current_level_xp = st.session_state.xp % 100
    level_progress = current_level_xp / 100
    st.markdown(f"""
    <div class="hero">
        <div class="hero-tag">YOUR PERSONAL LEARNING HUB</div>
        <div class="hero-title">Welcome back, {player_name.split()[0]} 👋</div>
        <div class="hero-desc">
            Your next level is one quest away. Learn at your pace, build your skills,
            and turn every practice session into progress.
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:20px;align-items:center">
            <span class="badge">LEVEL {st.session_state.level} EXPLORER</span>
            <span style="color:#ffe09a;font-size:13px;font-weight:800">⚡ {st.session_state.xp} TOTAL XP</span>
            <span style="color:#b8f5e7;font-size:13px;font-weight:800">🔥 {st.session_state.best_streak} BEST STREAK</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # =====================================================
    # TOP STATS
    # =====================================================

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">⭐ Experience</div>
            <div class="stat-value">{st.session_state.xp} XP</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">🪙 Coins</div>
            <div class="stat-value">{st.session_state.coins}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">🏆 Current Level</div>
            <div class="stat-value">{st.session_state.level}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        accuracy = (
            round(
                (st.session_state.correct / st.session_state.total_answered) * 100
            )
            if st.session_state.total_answered > 0
            else 0
        )

        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">🎯 Accuracy</div>
            <div class="stat-value">{accuracy}%</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    # =====================================================
    # MISSIONS
    # =====================================================

    st.markdown('<div class="section-label">EXPLORE YOUR LEARNING WORLDS</div>',
                unsafe_allow_html=True)

    st.write("")

    mission1, mission2, mission3 = st.columns(3)

    with mission1:
        st.markdown("""
        <div class="mission-card">
            <div class="mission-icon">🐍</div>
            <div class="mission-name">Code Academy</div>
            <div class="mission-desc">
                Master programming concepts and solve coding challenges.
            </div>
            <br>
            <span class="badge">PROGRAMMING</span>
        </div>
        """, unsafe_allow_html=True)

    with mission2:
        st.markdown("""
        <div class="mission-card">
            <div class="mission-icon">🧠</div>
            <div class="mission-name">AI Universe</div>
            <div class="mission-desc">
                Explore artificial intelligence and machine learning.
            </div>
            <br>
            <span class="badge">TECHNOLOGY</span>
        </div>
        """, unsafe_allow_html=True)

    with mission3:
        st.markdown("""
        <div class="mission-card">
            <div class="mission-icon">🌎</div>
            <div class="mission-name">Knowledge World</div>
            <div class="mission-desc">
                Test your knowledge with science and general challenges.
            </div>
            <br>
            <span class="badge">DISCOVERY</span>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    st.markdown("---")

    # =====================================================
    # MISSION SELECTION
    # =====================================================

    st.markdown("## 🚀 Choose your next quest")
    st.caption("Pick a subject and difficulty. Your next challenge is ready when you are.")

    col1, col2 = st.columns(2)

    with col1:

        subject = st.selectbox(
            "1. Choose a subject",
            list(questions.keys()),
            help="Select the topic you want to practise."
        )

    with col2:

        difficulty = st.selectbox(
            "2. Choose difficulty",
            ["Easy", "Medium", "Hard"],
            help="Easy gives 10 XP, Medium 20 XP, and Hard 30 XP for a correct answer."
        )

    rewards = {
        "Easy": 10,
        "Medium": 20,
        "Hard": 30
    }

    reward_xp = rewards[difficulty]

    st.markdown(f"""
    <div class="quest-card">
        <span class="badge">{difficulty.upper()} MODE</span>
        <h3>🎯 Mission Reward</h3>
        <p style="color:#a5b4c9">
            Complete the challenge to earn
            <b style="color:#a5b4fc">{reward_xp} XP</b>
            and <b style="color:#fbbf24">5 coins 🪙</b>.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("⚔️ BEGIN QUEST", type="primary", use_container_width=True):

        st.session_state.subject = subject
        st.session_state.difficulty = difficulty

        st.session_state.question = random.choice(questions[subject])

        st.session_state.answered = False
        st.session_state.feedback = None
        st.session_state.hint_used = False
        st.session_state.question_round = st.session_state.get("question_round", 0) + 1

        st.rerun()

    # =====================================================
    # ACTIVE CHALLENGE - PHASE 3 UX
    # =====================================================

    if st.session_state.question:
        q = st.session_state.question
        round_number = st.session_state.get("question_round", 1)
        st.markdown("## 🎮 Active challenge")
        st.caption("Stay focused. Select an answer, submit it, then review the explanation.")
        st.markdown(f"""
        <div class="quiz-topline"><span>🧩 {st.session_state.subject.upper()}</span><span>⚡ {st.session_state.difficulty.upper()} · REWARD {reward_xp} XP</span></div>
        <div class="quiz-panel"><div style="color:#9ea8ff;font-weight:800;letter-spacing:1px;font-size:11px">YOUR CHALLENGE</div>
        <div class="quiz-question">{q['q']}</div></div>
        """, unsafe_allow_html=True)
        st.write("")

        selected = st.radio(
            "Choose your answer", q["options"],
            key=f"answer_choice_{round_number}",
            disabled=st.session_state.answered,
            label_visibility="visible"
        )

        hint_col, submit_col = st.columns([1, 1.35])
        with hint_col:
            if not st.session_state.answered and st.button("💡 Reveal hint", use_container_width=True):
                st.session_state.hint_used = True
                st.rerun()
        with submit_col:
            if not st.session_state.answered and st.button("Submit answer  →", type="primary", use_container_width=True):
                st.session_state.answered = True
                st.session_state.total_answered += 1
                if selected == q["answer"]:
                    st.session_state.correct += 1
                    st.session_state.streak += 1
                    st.session_state.best_streak = max(st.session_state.best_streak, st.session_state.streak)
                    earned_xp = reward_xp if not st.session_state.hint_used else max(5, reward_xp - 5)
                    st.session_state.xp += earned_xp
                    st.session_state.coins += 5
                    st.session_state.level = st.session_state.xp // 100 + 1
                    st.session_state.feedback = "correct"
                    save_player_attempt(st.session_state.authenticated_user["user_id"], st.session_state.subject, "Daily Challenge", st.session_state.difficulty, q["q"], True, earned_xp)
                else:
                    st.session_state.streak = 0
                    st.session_state.feedback = "incorrect"
                    save_player_attempt(st.session_state.authenticated_user["user_id"], st.session_state.subject, "Daily Challenge", st.session_state.difficulty, q["q"], False, 0)
                persist_player_profile(st.session_state.authenticated_user["user_id"], st.session_state.xp, st.session_state.coins, st.session_state.best_streak)
                st.rerun()

        if st.session_state.hint_used and not st.session_state.answered:
            st.info("💡 Hint: " + q["hint"])

        if st.session_state.answered:
            if st.session_state.feedback == "correct":
                earned_display = reward_xp if not st.session_state.hint_used else max(5, reward_xp - 5)
                st.markdown(f"""<div class="quiz-feedback-good"><h3 style="margin:0;color:#77e9c7">✓ Correct answer!</h3>
                <p style="margin:8px 0 0;color:#c8f7e9">Great job, {html.escape(player_name.split()[0])}! You earned <b>+{earned_display} XP</b> and <b>+5 coins</b>.</p></div>""", unsafe_allow_html=True)
                st.balloons()
            else:
                st.markdown(f"""<div class="quiz-feedback-bad"><h3 style="margin:0;color:#ff9baa">✕ Not quite</h3>
                <p style="margin:8px 0 0;color:#f5cbd2">The correct answer is <b>{html.escape(str(q['answer']))}</b>. Keep going—mistakes are part of learning.</p></div>""", unsafe_allow_html=True)
            st.markdown(f"""<div class="quiz-explanation"><div style="font-weight:800;color:#ffd27b;margin-bottom:8px">📘 WHY THIS IS CORRECT</div><div style="color:#d7def2;line-height:1.65">{html.escape(str(q['explanation']))}</div></div>""", unsafe_allow_html=True)
            if st.button("Next challenge  →", type="primary", use_container_width=True):
                st.session_state.question = random.choice(questions[st.session_state.subject])
                st.session_state.answered = False
                st.session_state.feedback = None
                st.session_state.hint_used = False
                st.session_state.question_round = round_number + 1
                st.rerun()

    # =====================================================
    # FOOTER
    # =====================================================

    st.markdown("---")

    st.markdown("""
    <div style="text-align:center;color:#64748b;padding:15px">
        KNOWLEDGE QUEST · LEARN THROUGH PLAY · LEVEL UP YOUR MIND
    </div>
    """, unsafe_allow_html=True)
\

# =====================================================
# PHASE 6 - MOCK TESTS
# =====================================================

if selected_page == "Mock Tests":
    st.markdown("## 📝 Mock Test Arena")
    st.caption("Timed exam simulation using the built-in question bank. Your responses are recorded in analytics after you submit or the timer expires.")

    mock_subjects = list(questions.keys()) + ["Mixed Subjects"]
    if not st.session_state.mock_test_active and not st.session_state.mock_test_completed:
        with st.container(border=True):
            st.markdown("### Configure your test")
            setup_a, setup_b, setup_c = st.columns(3)
            with setup_a:
                mock_subject = st.selectbox("Subject", mock_subjects, key="mock_setup_subject")
            with setup_b:
                available_count = sum(len(qs) for qs in questions.values()) if mock_subject == "Mixed Subjects" else len(questions[mock_subject])
                max_questions = max(3, min(available_count, 15))
                mock_count = st.slider("Questions", 3, max_questions, min(5, max_questions), key="mock_setup_count")
            with setup_c:
                mock_minutes = st.slider("Time limit (minutes)", 5, 30, 10, key="mock_setup_minutes")
            mock_title = st.text_input("Test name", value="Placement Practice Test", max_chars=60, key="mock_setup_name")
            st.info(f"{mock_count} questions · {mock_minutes} minutes · no hints during test · review answers after submission")
            if st.button("🚀 Start Mock Test", type="primary", use_container_width=True):
                if mock_subject == "Mixed Subjects":
                    pool = [(subject_name, item) for subject_name, qs in questions.items() for item in qs]
                else:
                    pool = [(mock_subject, item) for item in questions[mock_subject]]
                picked = random.sample(pool, min(mock_count, len(pool)))
                st.session_state.mock_test_questions = [{"subject": subj, **item} for subj, item in picked]
                st.session_state.mock_test_answers = {}
                st.session_state.mock_test_review = []
                st.session_state.mock_test_index = 0
                st.session_state.mock_test_started_at = __import__("time").time()
                st.session_state.mock_test_duration_seconds = mock_minutes * 60
                st.session_state.mock_test_subject = mock_subject
                st.session_state.mock_test_name = (mock_title.strip() or "Placement Practice Test")
                st.session_state.mock_test_active = True
                st.session_state.mock_test_completed = False
                st.session_state.mock_test_result_saved = False
                st.session_state.mock_test_id += 1
                st.rerun()

    def render_mock_exam():
        if not st.session_state.mock_test_questions:
            return
        test_items = st.session_state.mock_test_questions
        total_q = len(test_items)
        current_i = min(st.session_state.mock_test_index, total_q - 1)
        elapsed = int(__import__("time").time() - st.session_state.mock_test_started_at)
        remaining = max(0, st.session_state.mock_test_duration_seconds - elapsed)
        st.session_state.mock_test_elapsed = elapsed
        if remaining <= 0 and st.session_state.mock_test_active:
            st.session_state.mock_test_active = False
            st.session_state.mock_test_completed = True
            st.session_state.mock_test_timed_out = True
            st.rerun()

        if st.session_state.mock_test_active:
            st.markdown("### " + st.session_state.mock_test_name)
            timer_col, progress_col = st.columns([1, 2])
            with timer_col:
                st.metric("⏱ Time remaining", f"{remaining // 60:02d}:{remaining % 60:02d}")
            with progress_col:
                answered_count = len(st.session_state.mock_test_answers)
                st.progress(answered_count / total_q)
                st.caption(f"Answered {answered_count} of {total_q} · Question {current_i + 1} of {total_q}")
            status_cols = st.columns(min(total_q, 10))
            for num in range(total_q):
                with status_cols[num % len(status_cols)]:
                    status = "🟩" if num in st.session_state.mock_test_answers else ("🟨" if num in st.session_state.mock_test_review else "⬜")
                    if st.button(f"{status} {num + 1}", key=f"mock_nav_{st.session_state.mock_test_id}_{num}", use_container_width=True):
                        st.session_state.mock_test_index = num
                        st.rerun()
            q_item = test_items[current_i]
            st.markdown(f"**Question {current_i + 1} · {q_item['subject']}**")
            st.markdown(f"<div class='quiz-panel'><div class='quiz-question'>{html.escape(str(q_item['q']))}</div></div>", unsafe_allow_html=True)
            existing_answer = st.session_state.mock_test_answers.get(current_i)
            selected_option = st.radio("Select an answer", q_item["options"], index=q_item["options"].index(existing_answer) if existing_answer in q_item["options"] else None, key=f"mock_answer_{st.session_state.mock_test_id}_{current_i}", label_visibility="collapsed")
            if selected_option:
                st.session_state.mock_test_answers[current_i] = selected_option
            nav1, nav2, nav3, nav4 = st.columns(4)
            with nav1:
                if st.button("← Previous", disabled=current_i == 0, use_container_width=True):
                    st.session_state.mock_test_index -= 1
                    st.rerun()
            with nav2:
                review_label = "⭐ Unmark review" if current_i in st.session_state.mock_test_review else "⭐ Mark review"
                if st.button(review_label, use_container_width=True):
                    if current_i in st.session_state.mock_test_review:
                        st.session_state.mock_test_review.remove(current_i)
                    else:
                        st.session_state.mock_test_review.append(current_i)
                    st.rerun()
            with nav3:
                if st.button("Next →", disabled=current_i >= total_q - 1, use_container_width=True):
                    st.session_state.mock_test_index += 1
                    st.rerun()
            with nav4:
                if st.button("Finish test", type="primary", use_container_width=True):
                    st.session_state.mock_test_active = False
                    st.session_state.mock_test_completed = True
                    st.session_state.mock_test_timed_out = False
                    st.rerun()
            st.caption("Legend: 🟩 Answered · 🟨 Marked for review · ⬜ Not answered")

    if st.session_state.mock_test_active:
        # Fragment provides a live countdown on modern Streamlit; older versions still
        # enforce the time limit on the next user interaction/rerun.
        if hasattr(st, "fragment"):
            live_exam = st.fragment(run_every="1s")(render_mock_exam)
            live_exam()
        else:
            render_mock_exam()

    if st.session_state.mock_test_completed:
        test_items = st.session_state.mock_test_questions
        total_q = len(test_items)
        answers = st.session_state.mock_test_answers
        correct_n = sum(1 for idx, item in enumerate(test_items) if answers.get(idx) == item["answer"])
        wrong_n = sum(1 for idx, item in enumerate(test_items) if idx in answers and answers.get(idx) != item["answer"])
        blank_n = total_q - len(answers)
        pct = round(correct_n / total_q * 100) if total_q else 0
        elapsed = min(int(__import__("time").time() - st.session_state.mock_test_started_at), st.session_state.mock_test_duration_seconds)
        if not st.session_state.mock_test_result_saved:
            current_uid = st.session_state.authenticated_user["user_id"]
            for idx, item in enumerate(test_items):
                chosen = answers.get(idx)
                save_player_attempt(current_uid, item["subject"], "Mock Test: " + st.session_state.mock_test_name, "Timed", item["q"], chosen == item["answer"], 5 if chosen == item["answer"] else 0)
            save_mock_test_summary(current_uid, st.session_state.mock_test_name, st.session_state.mock_test_subject, total_q, correct_n, elapsed)
            # Mock test completion rewards are applied once per session.
            st.session_state.xp += correct_n * 5 + 10
            st.session_state.coins += 10
            st.session_state.correct += correct_n
            st.session_state.total_answered += total_q
            st.session_state.level = st.session_state.xp // 100 + 1
            persist_player_profile(current_uid, st.session_state.xp, st.session_state.coins, st.session_state.best_streak)
            st.session_state.mock_test_result_saved = True
        st.markdown("### 🏁 Mock Test Results")
        if st.session_state.get("mock_test_timed_out", False):
            st.warning("Time expired. Your answers have been submitted automatically.")
        rcols = st.columns(5)
        rcols[0].metric("Score", f"{correct_n}/{total_q}")
        rcols[1].metric("Accuracy", f"{pct}%")
        rcols[2].metric("Correct", correct_n)
        rcols[3].metric("Incorrect", wrong_n)
        rcols[4].metric("Unanswered", blank_n)
        st.success(f"Rewards: +{correct_n * 5 + 10} XP · +10 coins")
        st.caption(f"Time used: {elapsed // 60} min {elapsed % 60} sec")
        st.markdown("### Review answers")
        for idx, item in enumerate(test_items):
            chosen = answers.get(idx, "No answer")
            is_right = chosen == item["answer"]
            mark = "✅" if is_right else "❌" if idx in answers else "⬜"
            with st.expander(f"{mark} Q{idx + 1}: {item['q']}"):
                st.write("**Your answer:**", chosen)
                st.write("**Correct answer:**", item["answer"])
                st.write("**Explanation:**", item.get("explanation", ""))
        if st.button("Start another mock test", type="primary", use_container_width=True):
            st.session_state.mock_test_active = False
            st.session_state.mock_test_completed = False
            st.session_state.mock_test_questions = []
            st.session_state.mock_test_answers = {}
            st.session_state.mock_test_review = []
            st.rerun()

# =====================================================
# PHASE 8/9 - ADAPTIVE LEARNING + COMPETITION ARENA
# =====================================================
if selected_page == "Adaptive Learning & Arena":
    st.markdown("## 🧠 Adaptive Learning & 🏆 Quest Arena")
    st.caption("Recommendations use your saved practice attempts. The Arena leaderboard is local to accounts sharing this app/database—not an internet multiplayer service.")
    current_uid = st.session_state.authenticated_user["user_id"]
    attempts = get_player_attempts(current_uid)
    daily = get_daily_learning(current_uid)
    goal_target = 5
    st.markdown("### 📅 Daily Learning Goal")
    g1, g2, g3 = st.columns(3)
    g1.metric("Today's questions", f"{daily['attempts']}/{goal_target}")
    g2.metric("Today's correct", daily["correct"])
    g3.metric("Learning streak", f"🔥 {daily['streak']} day(s)")
    st.progress(min(daily["attempts"] / goal_target, 1.0))
    if daily["attempts"] >= goal_target:
        st.success("Daily goal completed! Great consistency—come back tomorrow to continue your streak.")
    else:
        st.info(f"Complete {goal_target-daily['attempts']} more question(s) to reach today's goal.")

    st.markdown("### 🗺️ Skill Tree / Mastery Map")
    topic_stats = {}
    for a in attempts:
        topic = classify_topic(a["question_text"])
        topic_stats.setdefault(topic, {"attempts":0,"correct":0})
        topic_stats[topic]["attempts"] += 1
        topic_stats[topic]["correct"] += int(a["is_correct"])
    topic_order = ["Basics & Syntax", "Object-Oriented Concepts", "AI & Machine Learning", "SQL & Database Concepts", "Networking", "General Knowledge", "Other Topics"]
    if not topic_stats:
        st.info("Your skill tree will grow after you answer questions in Dashboard, PDF Quests, or Mock Tests.")
    else:
        cards = st.columns(3)
        for i, topic in enumerate(topic_order):
            stats = topic_stats.get(topic, {"attempts":0,"correct":0})
            acc = round(stats["correct"] / stats["attempts"] * 100) if stats["attempts"] else 0
            if stats["attempts"] >= 5 and acc >= 80:
                status = "🟢 Mastered"
            elif stats["attempts"]:
                status = "🟡 In progress" if acc >= 50 else "🔴 Needs practice"
            else:
                status = "🔒 Not explored"
            with cards[i % 3]:
                st.markdown(f"**{topic}**")
                st.caption(status)
                st.progress(acc / 100 if stats["attempts"] else 0)
                st.caption(f"{acc}% accuracy · {stats['attempts']} attempts")

    st.markdown("### 🎯 Recommended Mission")
    if topic_stats:
        explored = [(t,v) for t,v in topic_stats.items() if v["attempts"]]
        weak_topic, weak_values = min(explored, key=lambda item: (item[1]["correct"] / item[1]["attempts"], -item[1]["attempts"]))
        weak_accuracy = round(weak_values["correct"] / weak_values["attempts"] * 100)
        weak_subject = None
        by_subject = {}
        for a in attempts:
            by_subject.setdefault(a["subject"], {"attempts":0,"correct":0})
            by_subject[a["subject"]]["attempts"] += 1
            by_subject[a["subject"]]["correct"] += int(a["is_correct"])
        weak_subject = min(by_subject, key=lambda subj: by_subject[subj]["correct"] / max(1,by_subject[subj]["attempts"]))
        st.warning(f"Focus suggestion: **{weak_topic}** ({weak_accuracy}% observed accuracy). Your weakest subject so far is **{weak_subject}**.")
        subject_bank = questions.get(weak_subject, [])
        if subject_bank:
            st.write("Start a focused mini-quest using the questions available for this subject.")
            if st.button("⚔️ Practice my weakest subject", type="primary"):
                picked = random.sample(subject_bank, min(3, len(subject_bank)))
                st.session_state.adaptive_practice_questions = [{"subject":weak_subject, **q} for q in picked]
                st.session_state.adaptive_practice_index = 0
                st.session_state.adaptive_practice_answers = {}
                st.session_state.adaptive_practice_started = True
                st.rerun()
    else:
        st.write("Complete a few questions first. Your recommendation will be based on your own attempt history.")

    if st.session_state.get("adaptive_practice_started", False):
        practice = st.session_state.adaptive_practice_questions
        ix = st.session_state.adaptive_practice_index
        if ix < len(practice):
            item = practice[ix]
            st.markdown(f"#### Focus Quest · Question {ix+1}/{len(practice)}")
            st.write(item["q"])
            feedback = st.session_state.get("adaptive_practice_feedback")
            if not feedback:
                choice = st.radio("Choose", item["options"], key=f"adaptive_choice_{ix}")
                if st.button("Submit answer", key=f"adaptive_submit_{ix}"):
                    st.session_state.adaptive_practice_answers[ix] = choice
                    is_right = choice == item["answer"]
                    save_player_attempt(current_uid, item["subject"], "Adaptive Focus Quest", "Adaptive", item["q"], is_right, 10 if is_right else 0)
                    if is_right:
                        st.session_state.xp += 10
                        st.session_state.coins += 3
                        st.session_state.correct += 1
                    st.session_state.total_answered += 1
                    st.session_state.level = st.session_state.xp // 100 + 1
                    st.session_state.adaptive_practice_feedback = (is_right, item["answer"], item.get("explanation", ""))
                    persist_player_profile(current_uid, st.session_state.xp, st.session_state.coins, st.session_state.best_streak)
                    st.rerun()
            else:
                if feedback[0]: st.success("Correct! +10 XP and +3 coins")
                else: st.error(f"Not quite. Correct answer: {feedback[1]}")
                if feedback[2]: st.write("Explanation:", feedback[2])
                if st.button("Next focus question", key=f"adaptive_next_{ix}"):
                    st.session_state.adaptive_practice_feedback = None
                    st.session_state.adaptive_practice_index += 1
                    st.rerun()
        else:
            st.success("Focus quest finished! Your new attempts have updated your mastery and recommendation.")
            if st.button("Close focus quest"):
                st.session_state.adaptive_practice_started = False
                st.rerun()

    st.markdown("---")
    st.markdown("### ⚡ Daily Challenge")
    today = __import__('datetime').date.today().isoformat()
    # Shared deterministic daily question for all accounts in this local installation.
    all_questions = [(subj, q) for subj, qs in questions.items() for q in qs]
    daily_index = int(hashlib.sha256(today.encode()).hexdigest(), 16) % len(all_questions)
    challenge_subject, challenge = all_questions[daily_index]
    challenge_hash = question_hash(challenge["q"])
    previous_result = get_daily_challenge_result(current_uid, today)
    st.write(f"**{challenge_subject}** · One attempt per account each day")
    st.markdown(f"#### {challenge['q']}")
    if previous_result is not None:
        st.success("You already attempted today's challenge: " + ("Correct 🎉" if previous_result[0] else "Incorrect. Come back tomorrow!"))
    else:
        daily_choice = st.radio("Challenge answer", challenge["options"], key="daily_challenge_choice")
        if st.button("Submit Daily Challenge", type="primary"):
            is_right = daily_choice == challenge["answer"]
            save_daily_challenge_result(current_uid, today, challenge_hash, is_right)
            save_player_attempt(current_uid, challenge_subject, "Daily Challenge", "Challenge", challenge["q"], is_right, 25 if is_right else 0)
            if is_right:
                st.session_state.xp += 25
                st.session_state.coins += 10
                st.session_state.correct += 1
            st.session_state.total_answered += 1
            st.session_state.level = st.session_state.xp // 100 + 1
            st.session_state.daily_challenge_feedback = (is_right, challenge["answer"], challenge.get("explanation", ""))
            persist_player_profile(current_uid, st.session_state.xp, st.session_state.coins, st.session_state.best_streak)
            st.rerun()
    if st.session_state.get("daily_challenge_feedback"):
        fb = st.session_state.daily_challenge_feedback
        st.success("Correct! Daily challenge reward: +25 XP, +10 coins") if fb[0] else st.error(f"Incorrect. Answer: {fb[1]}")
        if fb[2]: st.write(fb[2])

    st.markdown("### 🏆 Local Daily Challenge Leaderboard")
    st.caption("Leaderboard ranks accounts using the same local database. For online competition, the app would need a hosted backend and shared database.")
    leaders = get_daily_challenge_leaderboard(today)
    if leaders:
        leaderboard_rows = []
        for rank, row in enumerate(leaders, 1):
            user_tag = hashlib.sha256(str(row[0]).encode()).hexdigest()[:5].upper()
            leaderboard_rows.append({"Rank":rank,"Explorer":f"Explorer-{user_tag}","Result":"Correct" if row[1] else "Attempted","Submitted":row[2]})
        st.dataframe(leaderboard_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No challenge entries yet today. Be the first explorer!")

    st.markdown("### 🥇 Mock Test Rankings")
    with sqlite3.connect(QUEST_DB_PATH) as conn:
        ranking_rows = conn.execute("SELECT user_id, MAX(score_percent), COUNT(*), MAX(completed_at) FROM mock_test_history GROUP BY user_id ORDER BY MAX(score_percent) DESC, COUNT(*) DESC LIMIT 10").fetchall()
    if ranking_rows:
        ranks = [{"Rank":i,"Explorer":"Explorer-"+hashlib.sha256(str(r[0]).encode()).hexdigest()[:5].upper(),"Best score":f"{r[1]}%","Tests completed":r[2]} for i,r in enumerate(ranking_rows,1)]
        st.dataframe(ranks, use_container_width=True, hide_index=True)
    else:
        st.info("Complete a mock test to appear in the rankings.")

# =====================================================
# PHASE 7 - RELEASE SAFETY SETTINGS / READINESS
# =====================================================

if selected_page == "Mock Tests":
    st.markdown("---")
    st.markdown("### 🔐 Release readiness")
    st.caption("This is a local student app. Before publishing, set release mode and verify the checklist below.")
    release_mode = False
    try:
        release_mode = bool(st.secrets.get("RELEASE_MODE", False))
    except Exception:
        release_mode = False
    if release_mode:
        st.success("Release mode is enabled. Development OTPs should not be displayed in the authentication screen.")
    else:
        st.warning("Development mode is active. Local OTPs are shown for testing; do not deploy publicly in this mode.")
    release_checks = [
        "Use a strong, unique secret key and keep API keys outside app.py",
        "Configure real email/SMS OTP delivery before removing development OTP display",
        "Review auth.py password hashing, OTP expiry, and rate limiting",
        "Back up ai_quest.db before release and test restore procedures",
        "Test registration, login, forgot password, change password, and logout",
        "Test mobile layout and every navigation page",
        "Run the app from a clean virtual environment and verify dependencies",
        "Do not commit .streamlit/secrets.toml or database files with personal data",
    ]
    checked_release = st.session_state.get("release_checklist_checked", [])
    for idx, item in enumerate(release_checks):
        is_checked = st.checkbox(item, key=f"release_check_{idx}")
    st.caption("Checklist is a local review aid—not a security certification. The authentication implementation itself requires review of auth.py.")

# =====================================================
# CREATE QUEST FROM PDF - GROQ CLOUD AI
# =====================================================

if selected_page == "Create Quest from PDF":
    st.markdown("""
    <div class="hero">
        <div class="hero-tag">PERSONALIZED AI PRACTICE</div>
        <div class="hero-title">📄 Create a Quest from Your PDF</div>
        <div class="hero-desc">Upload your study notes and turn them into interactive practice missions using fast Groq cloud AI.</div>
    </div>
    """, unsafe_allow_html=True)

    # Read the API key from Streamlit secrets. Never place the key in app.py.
    try:
        groq_api_key = st.secrets.get("GROQ_API_KEY", "").strip()
    except Exception:
        groq_api_key = ""

    with st.container(border=True):
        st.markdown("### 01 · Add your study material")
        st.caption("Upload a text-based PDF. Knowledge Quest will read it and build a practice quest from its contents.")
        uploaded_pdf = st.file_uploader(
            "Choose a PDF file", type=["pdf"], key="quest_pdf_upload",
            help="Text-based PDFs are supported. Scanned/image-only PDFs need OCR."
        )
        if uploaded_pdf:
            st.caption(f"Selected: {uploaded_pdf.name} · {uploaded_pdf.size / 1024:.1f} KB")

    # Fetch the models that this exact API key can access. The result is cached
    # for five minutes to avoid calling the models endpoint on every interaction.
    available_models = []
    model_fetch_error = None
    if groq_api_key:
        try:
            available_models, model_fetch_error = fetch_groq_chat_models(groq_api_key)
        except requests.exceptions.RequestException as exc:
            model_fetch_error = str(exc)

    preferred_models = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "openai/gpt-oss-120b"]
    if available_models:
        default_model = next((m for m in preferred_models if m in available_models), available_models[0])
        default_index = available_models.index(default_model)
    else:
        default_index = 0

    with st.expander("⚙️ Groq AI settings", expanded=not bool(groq_api_key)):
        st.caption("AI provider: Groq Cloud · The app automatically discovers models available to your API key.")

        if available_models:
            groq_model = st.selectbox(
                "Available AI model",
                options=available_models,
                index=default_index,
                help="Only chat models returned by your Groq account are shown. The recommended model is selected by default."
            )
            st.success(f"Groq connected · {len(available_models)} chat models available")
        else:
            groq_model = None
            if not groq_api_key:
                st.warning("API key not found. Create .streamlit/secrets.toml and add GROQ_API_KEY = \"your_key\".")
            else:
                st.error("Could not retrieve the models available to this API key.")
                if model_fetch_error:
                    st.code(model_fetch_error[:2000])

        question_count = st.slider("Number of questions", 3, 10, 5)
        question_type = st.selectbox(
            "Question format", ["Multiple Choice (MCQ)", "True / False", "Fill in the blanks"]
        )
        difficulty_level = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=0)

        if groq_api_key and st.button("🔌 Refresh Groq models", use_container_width=True):
            fetch_groq_chat_models.clear()
            st.rerun()

    def extract_pdf_text(pdf_file):
        document = pymupdf.open(stream=pdf_file.getvalue(), filetype="pdf")
        try:
            pages_text = []
            for page in document:
                page_text = page.get_text("text")
                if page_text.strip():
                    pages_text.append(page_text)
            return "\n".join(pages_text).strip()
        finally:
            document.close()

    def parse_ai_json(content):
        cleaned = content.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                return json.loads(cleaned[start:end + 1])
            raise

    if uploaded_pdf:
        try:
            extracted_text = extract_pdf_text(uploaded_pdf)
            if extracted_text:
                st.success(f"PDF text extracted successfully · {len(extracted_text):,} characters")
                with st.expander("Preview extracted text"):
                    st.text(extracted_text[:5000])
                    if len(extracted_text) > 5000:
                        st.caption("Preview shortened. The AI uses the extracted text, subject to the input limit below.")
            else:
                st.error("No selectable text was found. This may be a scanned PDF; OCR support is not included yet.")
                extracted_text = ""
        except Exception as exc:
            st.error(f"Could not read this PDF: {exc}")
            extracted_text = ""

        if extracted_text:
            if len(extracted_text) > 40000:
                st.info("This PDF is long. The first 40,000 characters will be used for this initial version. Automatic multi-chunk generation can be added next.")

            if st.button("✨ Generate my quest", type="primary", use_container_width=True):
                if not groq_api_key:
                    st.error("Groq API key is missing. Add it to .streamlit/secrets.toml, save the file, and restart Streamlit.")
                elif not groq_model:
                    st.error("No available Groq chat model was found. Check your internet/API key and click Refresh Groq models.")
                else:
                    format_instructions = {
                        "Multiple Choice (MCQ)": 'Each question must have exactly four options and the answer must exactly match one option.',
                        "True / False": 'Each question must have options exactly ["True", "False"] and answer must be exactly "True" or "False".',
                        "Fill in the blanks": 'Each question must contain one blank written as "_____". Use an empty options array and provide the missing words as answer.'
                    }[question_type]

                    source_text = extracted_text[:40000]
                    source_hash = hashlib.sha256(uploaded_pdf.getvalue()).hexdigest()
                    current_user_id = st.session_state.authenticated_user["user_id"]
                    prior_questions = get_question_history(current_user_id, source_hash)
                    prior_questions = prior_questions[-60:]
                    avoid_text = "\n".join(f"- {q}" for q in prior_questions) if prior_questions else "(none yet)"
                    prompt = f"""Create {question_count} {difficulty_level.lower()} difficulty study questions using ONLY the source text below.
Question format: {question_type}.
Rules: {format_instructions}
Do not invent facts. Avoid duplicates. Keep questions clear and concise.
IMPORTANT: Do NOT repeat or paraphrase any question in the previously-used list. Create different questions testing different facts/concepts.
Previously used questions for this exact PDF and user:
{avoid_text}
Return ONLY valid JSON in this exact structure:
{{"questions":[{{"q":"question text","options":["A","B","C","D"],"answer":"exact answer","hint":"short hint","explanation":"brief explanation supported by source"}}]}}
For fill in the blanks, options must be []. Return exactly {question_count} questions if the source contains enough information.
SOURCE TEXT:
{source_text}
"""
                    payload = {
                        "model": groq_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You create accurate educational quizzes. Follow the requested JSON schema exactly. Return JSON only. Use only the supplied source text."
                            },
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.2,
                        "max_tokens": 3500,
                        "response_format": {"type": "json_object"},
                        "stream": False
                    }
                    try:
                        with st.spinner("⚡ Groq AI is reading your PDF and creating questions..."):
                            response = requests.post(
                                "https://api.groq.com/openai/v1/chat/completions",
                                headers={
                                    "Authorization": f"Bearer {groq_api_key}",
                                    "Content-Type": "application/json"
                                },
                                json=payload,
                                timeout=180
                            )

                        if not response.ok:
                            try:
                                error_detail = response.json()
                            except ValueError:
                                error_detail = response.text
                            st.error(f"Groq returned HTTP {response.status_code}.")
                            st.code(str(error_detail)[:4000])
                            if response.status_code == 401:
                                st.info("The API key is invalid or revoked. Create a new key in Groq Console and update .streamlit/secrets.toml.")
                            elif response.status_code == 404:
                                st.info("Groq could not find or access this model. Click Refresh Groq models and select a model returned by your account.")
                            elif response.status_code == 429:
                                st.info("Groq rate limit or free-tier quota reached. Wait for the limit to reset, or check usage in Groq Console.")
                            elif response.status_code == 400:
                                st.info("Check whether the selected model is currently available and supports JSON response format. Try another model from the selector.")
                        else:
                            result = response.json()
                            content = result["choices"][0]["message"]["content"]
                            parsed = parse_ai_json(content)
                            generated = parsed.get("questions", [])
                            valid_questions = []

                            def validate_and_add(items):
                                added = 0
                                for item in items:
                                    if not isinstance(item, dict):
                                        continue
                                    if not all(key in item for key in ["q", "options", "answer", "hint", "explanation"]):
                                        continue
                                    item["q"] = str(item["q"]).strip()
                                    if not isinstance(item.get("options"), list):
                                        continue
                                    item["options"] = [str(option).strip() for option in item["options"] if str(option).strip()]
                                    item["answer"] = str(item["answer"]).strip()
                                    item["hint"] = str(item["hint"]).strip()
                                    item["explanation"] = str(item["explanation"]).strip()
                                    if not item["q"] or not item["answer"]:
                                        continue
                                    if question_type != "Fill in the blanks" and item["answer"] not in item["options"]:
                                        continue
                                    if question_type == "Multiple Choice (MCQ)" and len(item["options"]) != 4:
                                        continue
                                    if question_type == "True / False" and item["options"] != ["True", "False"]:
                                        continue
                                    if question_type == "Fill in the blanks":
                                        item["options"] = []
                                    seen = prior_questions + [q["q"] for q in valid_questions]
                                    if is_duplicate_question(item["q"], seen):
                                        continue
                                    valid_questions.append(item)
                                    added += 1
                                return added

                            validate_and_add(generated)

                            # Ask Groq for replacements when duplicates/invalid questions leave the quiz short.
                            replacement_attempts = 0
                            while len(valid_questions) < question_count and replacement_attempts < 2:
                                missing_count = question_count - len(valid_questions)
                                replacement_attempts += 1
                                already_used = prior_questions + [q["q"] for q in valid_questions]
                                replacement_prompt = f"""Generate exactly {missing_count} NEW {difficulty_level.lower()} {question_type} questions using ONLY the source text.
Rules: {format_instructions}
Do not repeat, rephrase, or test the same fact as any question in this exclusion list:
{chr(10).join('- ' + q for q in already_used[-80:])}
Return only JSON: {{"questions":[{{"q":"question text","options":["A","B","C","D"],"answer":"exact answer","hint":"short hint","explanation":"source-based explanation"}}]}}
For fill-in-the-blanks, options must be []. Do not add anything outside JSON.
SOURCE TEXT:
{source_text}
"""
                                replacement_payload = dict(payload)
                                replacement_payload["messages"] = [
                                    {"role": "system", "content": "Generate novel, source-grounded quiz questions. Follow the JSON schema exactly. Return JSON only."},
                                    {"role": "user", "content": replacement_prompt}
                                ]
                                replacement_payload["temperature"] = 0.65
                                with st.spinner(f"🔄 Finding {missing_count} new question(s) to replace duplicates (attempt {replacement_attempts}/2)..."):
                                    replacement_response = requests.post(
                                        "https://api.groq.com/openai/v1/chat/completions",
                                        headers={
                                            "Authorization": f"Bearer {groq_api_key}",
                                            "Content-Type": "application/json"
                                        },
                                        json=replacement_payload,
                                        timeout=180
                                    )
                                if not replacement_response.ok:
                                    st.warning(f"Replacement generation stopped: Groq returned HTTP {replacement_response.status_code}.")
                                    break
                                replacement_content = replacement_response.json()["choices"][0]["message"]["content"]
                                replacement_parsed = parse_ai_json(replacement_content)
                                replacement_items = replacement_parsed.get("questions", [])
                                if validate_and_add(replacement_items) == 0:
                                    break

                            if not valid_questions:
                                st.error("Groq responded, but no unique questions matched the required format. Try another PDF section or question format.")
                                with st.expander("View AI response"):
                                    st.code(content[:5000])
                            else:
                                st.session_state.generated_questions = valid_questions
                                save_question_history(current_user_id, source_hash, [q["q"] for q in valid_questions])
                                st.session_state.generated_index = 0
                                st.session_state.generated_answered = False
                                st.session_state.generated_feedback = None
                                st.session_state.generated_hint_used = False
                                st.session_state.generated_correct_count = 0
                                st.session_state.generated_total_xp = 0
                                st.session_state.generated_missed_questions = []
                                st.session_state.generated_bonus_awarded = False
                                st.session_state.generated_completed = False
                                st.session_state.generated_user_answers = []
                                st.session_state.generated_pdf_name = uploaded_pdf.name
                                st.success(f"Quest created! {len(valid_questions)} unique questions are ready.")
                                if len(valid_questions) < question_count:
                                    st.warning(f"Only {len(valid_questions)} unique question(s) were available after two replacement attempts. The source may have limited unique content; try a different section or more pages.")
                                st.rerun()

                    except requests.exceptions.Timeout:
                        st.error("Groq took too long to respond. Try fewer questions or a shorter PDF.")
                    except requests.exceptions.ConnectionError:
                        st.error("Could not connect to Groq. Check your internet connection.")
                    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
                        st.error(f"Could not understand the Groq response: {exc}")

    # Generated question gameplay - Phase 3 focused flow
    generated_questions = st.session_state.generated_questions
    if generated_questions:
        st.markdown("---")
        current_index = st.session_state.generated_index
        current_q = generated_questions[current_index]
        total_count = len(generated_questions)
        st.markdown("## 🎮 Your AI-generated quest")
        st.markdown(f"<div class=\"quiz-topline\"><span>📄 {html.escape(str(st.session_state.generated_pdf_name))}</span><span>QUESTION {current_index + 1} / {total_count}</span></div>", unsafe_allow_html=True)
        st.progress((current_index + 1) / total_count)
        st.markdown(f"<div class=\"quiz-panel\"><div style=\"color:#9ea8ff;font-weight:800;letter-spacing:1px;font-size:11px\">SOURCE-BASED QUESTION</div><div class=\"quiz-question\">{html.escape(str(current_q['q']))}</div></div>", unsafe_allow_html=True)

        if current_q["options"]:
            answer_value = st.radio("Choose your answer", current_q["options"], key=f"pdf_answer_{current_index}", disabled=st.session_state.generated_answered)
        else:
            answer_value = st.text_input("Type your answer", key=f"pdf_answer_{current_index}", disabled=st.session_state.generated_answered, placeholder="Your answer…")

        hint_col, submit_col = st.columns([1, 1.35])
        with hint_col:
            if not st.session_state.generated_answered and st.button("💡 Hint", key=f"gen_hint_{current_index}", use_container_width=True):
                st.session_state.generated_hint_used = True
                st.rerun()
        with submit_col:
            if not st.session_state.generated_answered and st.button("Submit answer  →", key=f"gen_submit_{current_index}", type="primary", use_container_width=True):
                st.session_state.generated_answered = True
                normalized_user_answer = answer_value.strip()
                st.session_state.generated_user_answers.append(normalized_user_answer)
                if normalized_user_answer.casefold() == current_q["answer"].strip().casefold():
                    st.session_state.generated_feedback = "correct"
                    save_player_attempt(st.session_state.authenticated_user["user_id"], "PDF Quest", st.session_state.generated_pdf_name, "AI Generated", current_q["q"], True, 10)
                    st.session_state.xp += 10
                    st.session_state.generated_total_xp += 10
                    st.session_state.coins += 5
                    st.session_state.correct += 1
                    st.session_state.generated_correct_count += 1
                    st.session_state.total_answered += 1
                    st.session_state.streak += 1
                    st.session_state.best_streak = max(st.session_state.best_streak, st.session_state.streak)
                    st.session_state.level = st.session_state.xp // 100 + 1
                else:
                    st.session_state.generated_feedback = "incorrect"
                    save_player_attempt(st.session_state.authenticated_user["user_id"], "PDF Quest", st.session_state.generated_pdf_name, "AI Generated", current_q["q"], False, 0)
                    st.session_state.total_answered += 1
                    st.session_state.streak = 0
                    st.session_state.generated_missed_questions.append({
                        "q": current_q["q"],
                        "options": current_q.get("options", []),
                        "answer": current_q["answer"],
                        "user_answer": normalized_user_answer,
                        "hint": current_q.get("hint", ""),
                        "explanation": current_q.get("explanation", ""),
                        "source": st.session_state.generated_pdf_name
                    })
                persist_player_profile(st.session_state.authenticated_user["user_id"], st.session_state.xp, st.session_state.coins, st.session_state.best_streak)
                st.rerun()

        if st.session_state.generated_hint_used and not st.session_state.generated_answered:
            st.info("💡 Hint: " + current_q["hint"])
        if st.session_state.generated_answered:
            if st.session_state.generated_feedback == "correct":
                st.markdown("<div class=\"quiz-feedback-good\"><h3 style=\"margin:0;color:#77e9c7\">✓ Correct! +10 XP and +5 coins</h3><p style=\"color:#c8f7e9;margin:8px 0 0\">Nice work—keep your streak alive.</p></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class=\"quiz-feedback-bad\"><h3 style=\"margin:0;color:#ff9baa\">✕ Not quite</h3><p style=\"color:#f5cbd2;margin:8px 0 0\">Correct answer: <b>{html.escape(str(current_q['answer']))}</b></p></div>", unsafe_allow_html=True)
            st.markdown(f"<div class=\"quiz-explanation\"><div style=\"font-weight:800;color:#ffd27b;margin-bottom:8px\">📘 EXPLANATION</div><div style=\"color:#d7def2;line-height:1.65\">{html.escape(str(current_q['explanation']))}</div></div>", unsafe_allow_html=True)
            if current_index < total_count - 1:
                if st.button("Next question  →", key=f"gen_next_{current_index}", type="primary", use_container_width=True):
                    st.session_state.generated_index += 1
                    st.session_state.generated_answered = False
                    st.session_state.generated_feedback = None
                    st.session_state.generated_hint_used = False
                    st.rerun()
            else:
                # Award the completion bonus only once per generated quest.
                completion_bonus = 20 if st.session_state.generated_correct_count == total_count else 10
                if not st.session_state.generated_bonus_awarded:
                    st.session_state.xp += completion_bonus
                    st.session_state.coins += 10
                    st.session_state.generated_total_xp += completion_bonus
                    st.session_state.level = st.session_state.xp // 100 + 1
                    st.session_state.generated_bonus_awarded = True
                    st.session_state.generated_completed = True
                    persist_player_profile(st.session_state.authenticated_user["user_id"], st.session_state.xp, st.session_state.coins, st.session_state.best_streak)
                    st.balloons()
                correct_count = st.session_state.generated_correct_count
                incorrect_count = total_count - correct_count
                accuracy = round((correct_count / total_count) * 100) if total_count else 0
                badge_text = "🏆 Perfect Quest" if accuracy == 100 else ("🌟 Sharp Explorer" if accuracy >= 80 else ("🧭 Quest Finisher" if accuracy >= 50 else "💪 Keep Training"))
                st.markdown(f"""<div class="quiz-complete"><div style="color:#77e9c7;font-weight:800;letter-spacing:1.5px">QUEST COMPLETE</div><h2 style="margin:8px 0">Well played, {html.escape(player_name.split()[0])}!</h2><div class="reward-badge">{badge_text}</div><h1 style="font-size:40px;margin:8px">{correct_count}/{total_count}</h1><p style="color:#aeb9d7">Correct answers · {accuracy}% accuracy</p><div style="font-size:20px;color:#ffd27b;font-weight:800">+{st.session_state.generated_total_xp} XP total earned</div><p style="color:#c8f7e9;margin:8px 0 0">Completion bonus: +{completion_bonus} XP and +10 coins</p></div>""", unsafe_allow_html=True)
                st.markdown("### 📊 Quest performance")
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("Correct", f"{correct_count}/{total_count}")
                r2.metric("Incorrect", incorrect_count)
                r3.metric("Accuracy", f"{accuracy}%")
                r4.metric("XP earned", f"+{st.session_state.generated_total_xp}")
                if accuracy == 100:
                    st.success("Perfect run! Every answer was correct. Your Perfect Quest badge is earned for this run.")
                elif accuracy >= 80:
                    st.info("Excellent work! Review any missed questions to lock in your learning.")
                elif accuracy >= 50:
                    st.info("Good progress. A short revision round on missed questions will strengthen this topic.")
                else:
                    st.warning("This topic needs another practice round. Start with the revision queue below.")
                if st.session_state.generated_missed_questions:
                    st.markdown("### 🧠 Revision queue — missed questions")
                    st.caption("Your missed questions are collected here for review. Revisit the explanation before retrying.")
                    for miss_i, missed in enumerate(st.session_state.generated_missed_questions, start=1):
                        with st.expander(f"{miss_i}. {missed['q']}"):
                            st.markdown(f"**Your answer:** {missed['user_answer'] or 'No answer'}")
                            st.markdown(f"**Correct answer:** {missed['answer']}")
                            st.markdown(f"**Explanation:** {missed['explanation']}")
                    if st.button("🔁 Retry missed questions", key="gen_retry_missed", type="primary", use_container_width=True):
                        retry_items = st.session_state.generated_missed_questions.copy()
                        for item in retry_items:
                            item["q"] = "Revision: " + item["q"]
                        st.session_state.generated_questions = retry_items
                        st.session_state.generated_index = 0
                        st.session_state.generated_answered = False
                        st.session_state.generated_feedback = None
                        st.session_state.generated_hint_used = False
                        st.session_state.generated_correct_count = 0
                        st.session_state.generated_total_xp = 0
                        st.session_state.generated_missed_questions = []
                        st.session_state.generated_bonus_awarded = False
                        st.session_state.generated_completed = False
                        st.session_state.generated_user_answers = []
                        st.rerun()
                else:
                    st.markdown("### 🎯 No revision needed — you answered every question correctly!")
                if st.button("Create another quest", key="gen_restart", use_container_width=True):
                    st.session_state.generated_questions = []
                    st.session_state.generated_index = 0
                    st.session_state.generated_answered = False
                    st.session_state.generated_feedback = None
                    st.session_state.generated_hint_used = False
                    st.session_state.generated_missed_questions = []
                    st.session_state.generated_bonus_awarded = False
                    st.session_state.generated_completed = False
                    st.session_state.generated_user_answers = []
                    st.rerun()

