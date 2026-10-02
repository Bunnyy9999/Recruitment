import os
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000").rstrip("/")


def apply_styles() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
    :root { --ink:#172321; --muted:#6e7d78; --paper:#f7f8f4; --line:#e3e9e3; --leaf:#236b53; --mint:#dcefe2; --coral:#ed795c; --night:#172321; }
    html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
    .stApp { background:var(--paper); color:var(--ink); }
    [data-testid="stSidebar"] { background:#eef3ed; border-right:1px solid var(--line); }
    [data-testid="stSidebar"] > div:first-child { padding:2rem 1.1rem; }
    h1,h2,h3 { font-family:'Space Grotesk',sans-serif !important; color:var(--ink); letter-spacing:0 !important; }
    h1 { font-size:2.55rem !important; line-height:1.05 !important; }
    p,label,[data-testid="stCaptionContainer"] { color:var(--muted); }
    .brand { padding:.25rem .35rem 2.2rem; }
    .brand-mark { color:var(--coral); font-size:1.8rem; line-height:1; }
    .brand-name { font:700 1.25rem 'Space Grotesk',sans-serif; color:var(--ink); margin-left:.35rem; }
    .eyebrow { text-transform:uppercase; letter-spacing:.12em; font-size:.68rem; font-weight:700; color:var(--leaf); margin-bottom:.4rem; }
    .hero { background:var(--night); color:white; border-radius:18px; padding:2rem 2.2rem; margin:.4rem 0 1.5rem; position:relative; overflow:hidden; }
    .hero:after { content:''; position:absolute; width:220px; height:220px; right:-60px; top:-90px; border:35px solid #f4c95d; border-radius:50%; }
    .hero h1 { color:white !important; max-width:690px; margin:.2rem 0 .7rem; }
    .hero p { color:#b7c8bf; max-width:620px; margin:0; }
    .metric { background:white; border:1px solid var(--line); border-radius:14px; padding:1.1rem 1.2rem; min-height:105px; }
    .metric-value { font:700 2rem 'Space Grotesk',sans-serif; color:var(--ink); }
    .metric-label { font-size:.76rem; color:var(--muted); margin-top:.2rem; }
    .dashboard-header { display:flex; flex-direction:column; justify-content:center; min-height:76px; }
    .dashboard-brand-name { font:700 1.35rem 'Space Grotesk',sans-serif; color:var(--ink); }
    .dashboard-title { color:var(--muted); font-size:.8rem; font-weight:600; margin-top:.1rem; }
    .dashboard-card { --metric-accent:#24745c; --metric-tint:#eef7f2; min-height:148px; padding:1.1rem 1.2rem; border:1px solid var(--line); border-top:3px solid var(--metric-accent); border-radius:10px; background:linear-gradient(145deg,#fff 68%,var(--metric-tint)); box-shadow:0 2px 7px rgba(23,35,33,.035); transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease; animation:dashboard-enter .45s ease both; }
    .dashboard-card:hover { box-shadow:0 12px 24px rgba(23,35,33,.09); }
    .dashboard-card:nth-child(3n+2) { animation-delay:.07s; }
    .dashboard-card:nth-child(3n) { animation-delay:.14s; }
    .dashboard-card.jobs-closed { --metric-accent:#718078; --metric-tint:#f1f3f1; }
    .dashboard-card.applicants { --metric-accent:#2670a8; --metric-tint:#eef5fa; }
    .dashboard-card.stage-one { --metric-accent:#24917c; --metric-tint:#edf8f5; }
    .dashboard-card.first-interview { --metric-accent:#c27c22; --metric-tint:#fbf5e9; }
    .dashboard-card.second-interview { --metric-accent:#5473b4; --metric-tint:#f0f3fa; }
    .dashboard-card.ceo-review { --metric-accent:#765ca1; --metric-tint:#f4f1f8; }
    .dashboard-card.successful { --metric-accent:#28794d; --metric-tint:#eef7ef; }
    .dashboard-card.ceo-failed { --metric-accent:#bf5748; --metric-tint:#fbf0ed; }
    .dashboard-card-label { color:#52635d; font-size:.82rem; font-weight:600; line-height:1.35; min-height:2.3em; }
    .dashboard-card-value { color:var(--ink); font:700 2.35rem 'Space Grotesk',sans-serif; line-height:1; margin:.8rem 0 .45rem; }
    .dashboard-card-note { color:#78857f; font-size:.72rem; }
    div[class*="st-key-dashboard-card-wrap"] .stButton > button { display:flex; align-items:stretch; min-height:148px; padding:1rem 1.15rem; border:1px solid var(--line); border-top:3px solid #24745c; border-radius:10px; background:linear-gradient(145deg,#fff 68%,#eef7f2); box-shadow:0 2px 7px rgba(23,35,33,.035); transition:box-shadow .2s ease; }
    div[class*="st-key-dashboard-card-wrap-jobs-draft"] .stButton > button { border-top-color:#c27c22; background:linear-gradient(145deg,#fff 68%,#fbf5e9); }
    div[class*="st-key-dashboard-card-wrap-jobs-open"] .stButton > button { border-top-color:#2670a8; background:linear-gradient(145deg,#fff 68%,#eef5fa); }
    div[class*="st-key-dashboard-card-wrap-jobs-closed"] .stButton > button { border-top-color:#718078; background:linear-gradient(145deg,#fff 68%,#f1f3f1); }
    div[class*="st-key-dashboard-card-wrap-stage-one"] .stButton > button { border-top-color:#24917c; background:linear-gradient(145deg,#fff 68%,#edf8f5); }
    div[class*="st-key-dashboard-card-wrap-first-interview"] .stButton > button { border-top-color:#c27c22; background:linear-gradient(145deg,#fff 68%,#fbf5e9); }
    div[class*="st-key-dashboard-card-wrap-second-interview"] .stButton > button { border-top-color:#5473b4; background:linear-gradient(145deg,#fff 68%,#f0f3fa); }
    div[class*="st-key-dashboard-card-wrap-ceo-review"] .stButton > button { border-top-color:#765ca1; background:linear-gradient(145deg,#fff 68%,#f4f1f8); }
    div[class*="st-key-dashboard-card-wrap-successful"] .stButton > button { border-top-color:#28794d; background:linear-gradient(145deg,#fff 68%,#eef7ef); }
    div[class*="st-key-dashboard-card-wrap-ceo-failed"] .stButton > button { border-top-color:#bf5748; background:linear-gradient(145deg,#fff 68%,#fbf0ed); }
    div[class*="st-key-dashboard-card-wrap"] .stButton > button p { margin:0; text-align:left; white-space:pre-wrap; }
    div[class*="st-key-dashboard-card-wrap"] .stButton > button p:nth-of-type(1) { color:#52635d; font-size:.82rem; font-weight:600; line-height:1.35; }
    div[class*="st-key-dashboard-card-wrap"] .stButton > button p:nth-of-type(2) { color:var(--ink); font:700 2.25rem 'Space Grotesk',sans-serif; line-height:1.15; margin:.65rem 0 .3rem; }
    div[class*="st-key-dashboard-card-wrap"] .stButton > button p:nth-of-type(3) { color:#78857f; font-size:.72rem; font-weight:400; }
    div[class*="st-key-dashboard-card-wrap"] .stButton > button:hover { box-shadow:0 12px 24px rgba(23,35,33,.09); border-color:#a8b9ad; }
    @keyframes dashboard-enter { from { opacity:0; transform:translateY(9px); } to { opacity:1; transform:translateY(0); } }
    @media (max-width:700px) { .dashboard-card { min-height:130px; padding:.95rem; } .dashboard-card-value { font-size:2rem; } }
    @media (prefers-reduced-motion:reduce) { .dashboard-card { animation:none; transition:none; } }
    .record { background:white; border:1px solid var(--line); border-radius:12px; padding:.8rem 1rem; margin-bottom:.55rem; }
    .record-title { font-weight:700; color:var(--ink); }
    .record-meta { color:var(--muted); font-size:.78rem; margin-top:.2rem; }
    .status-pill { display:inline-block; border-radius:999px; padding:.22rem .62rem; font-size:.72rem; font-weight:700; background:var(--mint); color:var(--leaf); }
    .status-pill.fail { background:#fde4dc; color:#a94731; }
    .status-pill.pending { background:#fff1c7; color:#85651b; }
    .stButton > button { border-radius:9px; border:1px solid #c8d8ca; color:var(--leaf); font-weight:700; background:white; min-height:2.55rem; }
    .stButton > button[kind="primary"] { background:var(--leaf); color:white; border-color:var(--leaf); }
    .stButton > button:hover { border-color:var(--coral); color:var(--coral); }
    div[data-testid="stForm"] { background:white; border:1px solid var(--line); border-radius:14px; padding:1.1rem; }
    .stTextInput input,.stTextArea textarea,.stNumberInput input,.stDateInput input,.stTimeInput input { border-radius:8px; border-color:#d4dfd5; }
    .small-note { font-size:.78rem; color:var(--muted); }
    </style>
    """, unsafe_allow_html=True)


def setup_page(title: str) -> None:
    st.set_page_config(page_title=f"DataRopes | {title}", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
    apply_styles()


class APIError(RuntimeError):
    pass


def api_request(method: str, path: str, **kwargs: Any) -> Any:
    url = path if path.startswith("http") else f"{API_URL}{path}"
    try:
        response = requests.request(method, url, timeout=45, **kwargs)
    except requests.RequestException as error:
        raise APIError(f"Backend unavailable at {API_URL}") from error
    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise APIError(f"{response.status_code}: {detail}")
    return response.json() if response.content else None


def get_json(path: str, **kwargs: Any) -> Any:
    return api_request("GET", path, **kwargs)


def post_json(path: str, payload: dict[str, Any] | None = None, **kwargs: Any) -> Any:
    return api_request("POST", path, json=payload, **kwargs)


def patch_json(path: str, payload: dict[str, Any]) -> Any:
    return api_request("PATCH", path, json=payload)


def safe_api(call: Any, *, success: str | None = None) -> Any | None:
    try:
        result = call()
    except APIError as error:
        st.error(str(error))
        return None
    if success:
        st.success(success)
    return result


def load_jobs() -> list[dict[str, Any]]:
    try:
        return get_json("/api/v1/jobs") or []
    except APIError:
        return []


def job_options(jobs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {f"{job['title']} · {job['status'].title()}": job for job in jobs}


def fmt_status(value: str | None) -> str:
    return (value or "unknown").replace("_", " ").title()


def status_badge(value: str | None) -> str:
    normalized = value or "pending"
    flavor = "fail" if normalized in {"fail", "failed_at_sync", "closed_complete"} else "pending" if normalized in {"pending", "pending_ceo_decision"} else ""
    return f'<span class="status-pill {flavor}">{fmt_status(value)}</span>'


def render_sidebar() -> None:
    st.sidebar.markdown('<div class="brand"><span class="brand-mark">◈</span><span class="brand-name">DataRopes</span></div>', unsafe_allow_html=True)
    st.sidebar.caption("Recruitment workspace")
    st.sidebar.markdown("**Workspace**")
    st.sidebar.page_link("main.py", label="Dashboard", icon="📊")
    st.sidebar.page_link("pages/0_🏢_Jobs_Dashboard.py", label="Jobs Dashboard", icon="🏢")
    st.sidebar.page_link("pages/1_🎯_Hiring_Request.py", label="Hiring Request", icon="🎯")
    st.sidebar.page_link("pages/2_🔄_Sync_&_Screen.py", label="Sync & Screen", icon="🔄")
    st.sidebar.page_link("pages/3_🎙️_Interviews.py", label="Interviews", icon="🎙️")
    st.sidebar.page_link("pages/4_💼_Executive.py", label="Executive Review", icon="💼")
    st.sidebar.divider()
    st.sidebar.markdown(f"<div class='small-note'>API<br><strong>{API_URL}</strong></div>", unsafe_allow_html=True)
    if st.sidebar.button("Refresh data", use_container_width=True):
        st.rerun()
