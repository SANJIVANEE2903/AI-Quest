
import streamlit as st
import random

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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

.stApp {
    background: #0b1020;
    color: #eef2ff;
    font-family: 'Inter', sans-serif;
}

header[data-testid="stHeader"] {
    background: transparent;
}

.block-container {
    padding-top: 1.8rem;
    padding-bottom: 3rem;
    max-width: 1250px;
}

[data-testid="stSidebar"] {
    background: #11182b;
    border-right: 1px solid #222d45;
}

[data-testid="stSidebar"] * {
    color: #e5eaff;
}

h1, h2, h3 {
    color: #f1f5ff !important;
    font-family: 'Inter', sans-serif;
}

p, label, span {
    font-family: 'Inter', sans-serif;
}

.quest-card {
    background: linear-gradient(135deg, #171f36, #11182b);
    border: 1px solid #293651;
    border-radius: 18px;
    padding: 24px;
    margin-bottom: 15px;
}

.hero {
    background: linear-gradient(120deg, #171c3c, #232451, #15263f);
    border: 1px solid #343d68;
    border-radius: 22px;
    padding: 30px;
    margin-bottom: 22px;
}

.hero-tag {
    color: #a5b4fc;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
}

.hero-title {
    font-size: 34px;
    font-weight: 800;
    margin-top: 10px;
    color: white;
}

.hero-desc {
    color: #bac5e4;
    font-size: 15px;
    margin-top: 8px;
}

.stat-card {
    background: #141d32;
    border: 1px solid #27344f;
    border-radius: 16px;
    padding: 18px;
    min-height: 100px;
}

.stat-label {
    font-size: 12px;
    color: #94a3c4;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.stat-value {
    font-size: 27px;
    font-weight: 800;
    color: #f1f5ff;
    margin-top: 6px;
}

.stat-icon {
    font-size: 20px;
}

.section-label {
    color: #9baed0;
    font-size: 12px;
    letter-spacing: 1.5px;
    font-weight: 700;
    text-transform: uppercase;
}

.mission-card {
    background: #141d32;
    border: 1px solid #293650;
    border-radius: 17px;
    padding: 20px;
    min-height: 175px;
}

.mission-icon {
    font-size: 27px;
    margin-bottom: 10px;
}

.mission-name {
    font-size: 17px;
    font-weight: 700;
    color: #eef2ff;
}

.mission-desc {
    color: #9aabc9;
    font-size: 13px;
    margin-top: 7px;
}

.badge {
    background: #242c51;
    border: 1px solid #414a7d;
    color: #b8c3ff;
    padding: 5px 10px;
    border-radius: 30px;
    font-size: 11px;
    font-weight: 700;
}

.question-box {
    background: linear-gradient(145deg, #17213a, #11192d);
    border: 1px solid #33415e;
    border-radius: 22px;
    padding: 30px;
}

.question-text {
    font-size: 23px;
    font-weight: 700;
    color: #f5f7ff;
    line-height: 1.5;
    margin: 20px 0;
}

.reward-box {
    background: #162c29;
    border: 1px solid #285548;
    border-radius: 15px;
    padding: 18px;
    color: #a7f3d0;
}

.warning-box {
    background: #30291b;
    border: 1px solid #66512c;
    border-radius: 15px;
    padding: 18px;
    color: #fcd58a;
}

div.stButton > button {
    border-radius: 12px;
    min-height: 46px;
    font-weight: 700;
    border: 1px solid #384867;
    background: #1a2540;
    color: #edf2ff;
    transition: 0.2s;
}

div.stButton > button:hover {
    border-color: #8b85ff;
    background: #273458;
    color: white;
}

div.stButton > button[kind="primary"] {
    background: linear-gradient(90deg, #6758e8, #8274ff);
    border: none;
    color: white;
}

div.stButton > button[kind="primary"]:hover {
    background: linear-gradient(90deg, #7869f4, #9488ff);
}

.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #7567f8, #37d9c4);
}

div[data-testid="stRadio"] > label {
    color: #cbd5e1;
    font-weight: 600;
}

hr {
    border-color: #25314a;
}

footer {
    visibility: hidden;
}

</style>
""", unsafe_allow_html=True)

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
    "hint_used": False
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# =====================================================
# PLAYER SIDEBAR
# =====================================================

with st.sidebar:

    st.markdown("## ⚔️ KNOWLEDGE QUEST")

    st.markdown("---")

    player_name = st.text_input(
        "PLAYER NAME",
        value="Student",
        key="player_name"
    )

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

        for key in defaults:
            st.session_state[key] = defaults[key]

        st.rerun()

# =====================================================
# MAIN DASHBOARD
# =====================================================

st.markdown("""
<div class="hero">
    <div class="hero-tag">YOUR LEARNING ADVENTURE STARTS HERE</div>
    <div class="hero-title">Welcome to Knowledge Quest ⚔️</div>
    <div class="hero-desc">
        Master new skills, complete missions, earn rewards,
        and become the ultimate knowledge explorer.
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

st.markdown('<div class="section-label">AVAILABLE MISSIONS</div>',
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

st.markdown("## 🚀 Start a Mission")

col1, col2 = st.columns(2)

with col1:

    subject = st.selectbox(
        "Choose your mission",
        list(questions.keys())
    )

with col2:

    difficulty = st.selectbox(
        "Select challenge difficulty",
        ["Easy", "Medium", "Hard"]
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

    st.rerun()

# =====================================================
# ACTIVE CHALLENGE
# =====================================================

if st.session_state.question:

    q = st.session_state.question

    st.markdown("---")

    st.markdown("## 🧩 Active Challenge")

    st.markdown(f"""
    <div class="question-box">
        <span class="badge">
            {st.session_state.subject.upper()}
        </span>
        <div class="question-text">
            {q['q']}
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.write("")

    selected = st.radio(
        "Choose your answer",
        q["options"],
        key="selected_option",
        label_visibility="collapsed"
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button("💡 Reveal Hint", use_container_width=True):

            st.session_state.hint_used = True

            st.info("💡 " + q["hint"])

    with col2:

        if st.button(
            "🚀 Submit Answer",
            type="primary",
            use_container_width=True
        ):

            if not st.session_state.answered:

                st.session_state.answered = True

                st.session_state.total_answered += 1

                if selected == q["answer"]:

                    st.session_state.correct += 1

                    st.session_state.streak += 1

                    st.session_state.best_streak = max(
                        st.session_state.best_streak,
                        st.session_state.streak
                    )

                    earned_xp = reward_xp

                    if st.session_state.hint_used:
                        earned_xp = max(5, earned_xp - 5)

                    st.session_state.xp += earned_xp

                    st.session_state.coins += 5

                    st.session_state.level = (
                        st.session_state.xp // 100 + 1
                    )

                    st.session_state.feedback = "correct"

                else:

                    st.session_state.streak = 0

                    st.session_state.feedback = "incorrect"

                st.rerun()

    # =================================================
    # FEEDBACK
    # =================================================

    if st.session_state.answered:

        if st.session_state.feedback == "correct":

            st.markdown(f"""
            <div class="reward-box">
                <h2>🎉 QUEST COMPLETED!</h2>
                <p>Excellent work, {player_name}!</p>
                <h3>+{reward_xp if not st.session_state.hint_used else max(5, reward_xp-5)} XP ⭐</h3>
                <h3>+5 Coins 🪙</h3>
            </div>
            """, unsafe_allow_html=True)

            st.balloons()

        else:

            st.markdown("""
            <div class="warning-box">
                <h3>⚠️ Mission Failed</h3>
                <p>Don't give up! Every mistake helps you learn.</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("### 📖 Learning Insight")

        st.write(q["explanation"])

        st.write(f"**Correct Answer:** {q['answer']}")

        if st.button("➡️ NEXT CHALLENGE", type="primary",
                     use_container_width=True):

            st.session_state.question = random.choice(
                questions[st.session_state.subject]
            )

            st.session_state.answered = False
            st.session_state.feedback = None
            st.session_state.hint_used = False

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
