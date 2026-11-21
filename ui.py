"""Knowledge Quest UI system.

Reusable presentation layer for the Streamlit application. This module contains
only UI styling and rendering helpers; it does not access or modify the database,
authentication, rewards, or question-generation logic.

Integration in app.py:
    import ui
    ui.apply_global_styles()

Use the render_* helpers where the corresponding page sections are displayed.
"""
from __future__ import annotations

from html import escape
from typing import Any, Iterable

import streamlit as st


THEME_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');
:root {
  --kq-bg:#090e1d;
  --kq-surface:#121a2d;
  --kq-surface-2:#19243c;
  --kq-border:rgba(159,174,220,.16);
  --kq-text:#f5f7ff;
  --kq-muted:#a8b3cf;
  --kq-purple:#9385ff;
  --kq-cyan:#55d9d0;
  --kq-gold:#ffc968;
  --kq-green:#54dfb5;
  --kq-red:#ff7d91;
}
.stApp {
  background:
    radial-gradient(ellipse at 8% 0%,rgba(119,101,255,.18),transparent 34%),
    radial-gradient(ellipse at 100% 14%,rgba(54,204,190,.09),transparent 28%),
    var(--kq-bg);
  color:var(--kq-text);
  font-family:'DM Sans',sans-serif;
}
header[data-testid="stHeader"] {background:transparent;}
.block-container {
  max-width:1460px;
  padding-top:1.35rem;
  padding-bottom:3rem;
  padding-left:clamp(1rem,3vw,2.7rem);
  padding-right:clamp(1rem,3vw,2.7rem);
}
[data-testid="stSidebar"] {
  background:linear-gradient(180deg,#151e35 0%,#0e1628 100%);
  border-right:1px solid var(--kq-border);
}
[data-testid="stSidebar"] * {color:#edf1ff;}
h1,h2,h3,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3 {
  font-family:'Space Grotesk',sans-serif;
  letter-spacing:-.45px;
  color:var(--kq-text)!important;
}
p,label,span {font-family:'DM Sans',sans-serif;}
.kq-eyebrow {
  color:var(--kq-cyan);font-size:10px;font-weight:800;
  letter-spacing:1.8px;text-transform:uppercase;
}
.kq-hero {
  position:relative;overflow:hidden;
  background:linear-gradient(112deg,#292957 0%,#202d50 57%,#155052 100%);
  border:1px solid rgba(151,140,255,.32);border-radius:26px;
  padding:clamp(23px,3.5vw,39px);margin:0 0 22px;
  box-shadow:0 22px 58px rgba(0,0,0,.22);
}
.kq-hero:after {
  content:'✦';position:absolute;right:5%;top:-28px;
  font-size:clamp(110px,16vw,180px);line-height:1;
  color:rgba(255,255,255,.055);transform:rotate(12deg);pointer-events:none;
}
.kq-hero-title {
  position:relative;z-index:1;font-family:'Space Grotesk',sans-serif;
  font-size:clamp(27px,3.2vw,41px);font-weight:700;line-height:1.16;
  color:#fff;max-width:900px;margin-top:9px;
}
.kq-hero-copy {
  position:relative;z-index:1;color:#d5def5;font-size:14px;
  line-height:1.7;max-width:740px;margin-top:11px;
}
.kq-chip {
  display:inline-flex;align-items:center;gap:6px;
  padding:6px 11px;border-radius:99px;
  background:rgba(147,133,255,.13);border:1px solid rgba(160,151,255,.3);
  color:#e2deff;font-size:10px;font-weight:800;letter-spacing:.7px;
}
.kq-stat {
  height:100%;min-height:116px;padding:18px 19px;border-radius:19px;
  background:linear-gradient(145deg,rgba(27,39,66,.98),rgba(16,25,44,.98));
  border:1px solid var(--kq-border);box-shadow:0 10px 26px rgba(0,0,0,.14);
  transition:transform .18s ease,border-color .18s ease;
}
.kq-stat:hover,.kq-feature:hover {transform:translateY(-3px);border-color:rgba(147,133,255,.52);}
.kq-stat-label {font-size:10px;color:var(--kq-muted);font-weight:800;letter-spacing:1px;text-transform:uppercase;}
.kq-stat-value {font-family:'Space Grotesk',sans-serif;font-size:clamp(23px,2.4vw,31px);font-weight:700;color:#fff;margin-top:9px;}
.kq-stat-foot {font-size:11px;color:#9daaca;margin-top:4px;}
.kq-section-label {font-size:10px;font-weight:800;letter-spacing:1.7px;color:var(--kq-cyan);text-transform:uppercase;}
.kq-feature {
  height:100%;min-height:184px;padding:21px;border-radius:20px;
  background:linear-gradient(150deg,rgba(28,40,68,.98),rgba(16,26,45,.98));
  border:1px solid var(--kq-border);box-shadow:0 10px 25px rgba(0,0,0,.13);
  transition:transform .18s ease,border-color .18s ease;
}
.kq-feature-icon {font-size:29px;margin-bottom:13px;}
.kq-feature-title {font-family:'Space Grotesk',sans-serif;font-size:17px;font-weight:700;color:#f5f6ff;}
.kq-feature-copy {font-size:12px;color:#b5c0da;line-height:1.65;margin-top:7px;}
.kq-panel {
  background:linear-gradient(145deg,rgba(26,38,65,.98),rgba(16,25,44,.98));
  border:1px solid var(--kq-border);border-radius:21px;padding:clamp(17px,2.5vw,25px);
  box-shadow:0 12px 28px rgba(0,0,0,.13);
}
.kq-question {font-family:'Space Grotesk',sans-serif;font-size:clamp(19px,2.1vw,27px);font-weight:600;line-height:1.45;color:#f7f8ff;margin:14px 0 8px;}
.kq-reward {background:linear-gradient(135deg,rgba(20,92,76,.28),rgba(17,54,54,.5));border:1px solid rgba(84,223,181,.34);border-radius:18px;padding:19px;color:#c1f8e9;}
.kq-warning {background:linear-gradient(135deg,rgba(111,75,24,.25),rgba(61,43,22,.45));border:1px solid rgba(255,201,104,.34);border-radius:18px;padding:19px;color:#ffe5b3;}
.stTextInput input,.stTextArea textarea,[data-baseweb="select"]>div {
  background:#151f36!important;color:#f4f6ff!important;
  border-color:#3b4869!important;border-radius:13px!important;
}
.stTextInput input:focus,.stTextArea textarea:focus {border-color:var(--kq-purple)!important;box-shadow:0 0 0 1px var(--kq-purple)!important;}
[data-testid="stFileUploader"] section {background:rgba(22,32,55,.8);border:1px dashed rgba(147,133,255,.58);border-radius:18px;padding:20px;}
[data-testid="stRadio"]>label {color:#dce5f8;font-weight:700;}
[data-testid="stRadio"] [role="radiogroup"] {gap:9px;}
[data-testid="stRadio"] [role="radio"] {background:rgba(23,34,58,.86);border:1px solid #354563;border-radius:13px;padding:11px 14px;margin-bottom:5px;}
[data-testid="stRadio"] [role="radio"]:hover {border-color:var(--kq-purple);}
div.stButton>button,.stFormSubmitButton>button {
  border-radius:13px;min-height:44px;font-weight:800;
  border:1px solid #3c4a70;background:#1b2745;color:#edf2ff;
  transition:all .18s ease;
}
div.stButton>button:hover,.stFormSubmitButton>button:hover {border-color:var(--kq-cyan);background:#223653;color:white;transform:translateY(-1px);}
div.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"] {
  background:linear-gradient(100deg,#8177ff,#9b8cff);border:0;color:#11152c;
  box-shadow:0 8px 20px rgba(104,104,245,.22);
}
div.stButton>button[kind="primary"]:hover,.stFormSubmitButton>button[kind="primary"]:hover {filter:brightness(1.08);}
.stProgress>div>div>div>div {background:linear-gradient(90deg,#9385ff,#55d9d0);}
hr {border-color:var(--kq-border);}
[data-testid="stMetric"] {background:rgba(23,34,58,.72);padding:13px;border-radius:15px;border:1px solid var(--kq-border);}
[data-testid="stAlert"] {border-radius:15px;}
[data-testid="stTabs"] button {font-weight:700;}
@media(max-width:700px) {
  .block-container {padding-top:1rem;padding-left:1rem;padding-right:1rem;}
  .kq-hero {border-radius:20px;}
  .kq-stat {min-height:98px;padding:14px;}
}
"""


def apply_global_styles() -> None:
    """Apply the Knowledge Quest theme once near the top of app.py."""
    st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)


def render_hero(title: str, description: str, eyebrow: str = "YOUR PERSONAL LEARNING HUB", chips: Iterable[str] = ()) -> None:
    """Render a wide gradient page hero with optional compact status chips."""
    chip_html = "".join(f'<span class="kq-chip">{escape(str(chip))}</span>' for chip in chips)
    st.markdown(
        f'''<section class="kq-hero">
          <div class="kq-eyebrow">{escape(eyebrow)}</div>
          <div class="kq-hero-title">{escape(title)}</div>
          <div class="kq-hero-copy">{escape(description)}</div>
          <div style="display:flex;flex-wrap:wrap;gap:9px;margin-top:19px;position:relative;z-index:1">{chip_html}</div>
        </section>''',
        unsafe_allow_html=True,
    )


def render_section_heading(title: str, caption: str | None = None, icon: str = "") -> None:
    """Render a consistent section heading."""
    st.markdown(f'<div class="kq-section-label">{escape(icon)} {escape(title)}</div>', unsafe_allow_html=True)
    if caption:
        st.caption(caption)


def render_stat_card(label: str, value: Any, footnote: str = "", icon: str = "") -> None:
    """Render a dashboard statistic card inside a Streamlit column."""
    st.markdown(
        f'''<div class="kq-stat">
          <div class="kq-stat-label">{escape(icon)} {escape(label)}</div>
          <div class="kq-stat-value">{escape(str(value))}</div>
          {f'<div class="kq-stat-foot">{escape(footnote)}</div>' if footnote else ''}
        </div>''',
        unsafe_allow_html=True,
    )


def render_feature_card(title: str, description: str, icon: str, tag: str = "") -> None:
    """Render a non-interactive feature/quest card; place its button separately."""
    tag_html = f'<div class="kq-section-label" style="margin-top:10px">{escape(tag)}</div>' if tag else ""
    st.markdown(
        f'''<div class="kq-feature">
          <div class="kq-feature-icon">{escape(icon)}</div>
          <div class="kq-feature-title">{escape(title)}</div>
          <div class="kq-feature-copy">{escape(description)}</div>
          {tag_html}
        </div>''',
        unsafe_allow_html=True,
    )


def render_panel(content: str, css_class: str = "kq-panel") -> None:
    """Render trusted, app-authored HTML inside a themed panel."""
    if css_class not in {"kq-panel", "kq-reward", "kq-warning"}:
        raise ValueError("Unsupported Knowledge Quest panel style")
    st.markdown(f'<div class="{css_class}">{content}</div>', unsafe_allow_html=True)


def render_level_progress(xp: int, level_size: int = 100, label: str = "Progress to next level") -> None:
    """Render level progress using Streamlit's accessible progress component."""
    safe_size = max(1, int(level_size))
    progress_xp = max(0, int(xp)) % safe_size
    st.caption(f"{label} · {progress_xp:,} / {safe_size:,} XP")
    st.progress(progress_xp / safe_size)
