from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "ucsi_pay_demo.db"

APP_TITLE = "UCSI Pay Demo"
MIN_TOP_UP = 10
MAX_WALLET_BALANCE = 200
PRESET_TOP_UPS = [10, 25, 50, 100, 150, 180]
GATE_LOCATIONS = ["Gate A", "Gate B", "Gate C"]
PAYMENT_LOCATIONS = [
    "Library Cafe",
    "Main Cafeteria",
    "UCSI Bookstore",
    "Campus Mart",
    "Event Booth",
]


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def now_local() -> datetime:
    return datetime.now().replace(microsecond=0)


def fmt_money(amount: float) -> str:
    prefix = "-" if amount < 0 else ""
    return f"{prefix}RM{abs(amount):,.2f}"


def fmt_balance(amount: float) -> str:
    return f"RM{amount:,.2f}"


def fmt_dt(value: str | None) -> str:
    if not value:
        return "-"
    return datetime.fromisoformat(value).strftime("%d %b %Y, %I:%M:%S %p")


def action_label(tx_type: str) -> str:
    labels = {
        "TOP_UP": "Top up",
        "ADMIN_TOP_UP": "Admin top up",
        "PAYMENT": "Merchant payment",
        "PARKING_ENTRY": "Parking entry",
        "PARKING_EXIT": "Parking fee",
    }
    return labels.get(tx_type, tx_type.replace("_", " ").title())


def amount_class(amount: float) -> str:
    if amount > 0:
        return "amount-positive"
    if amount < 0:
        return "amount-negative"
    return "amount-neutral"


def push_flash(kind: str, message: str) -> None:
    st.session_state.setdefault("flash_messages", []).append((kind, message))


def show_flash_messages() -> None:
    flashes = st.session_state.pop("flash_messages", [])
    for kind, message in flashes:
        if kind == "success":
            st.success(message)
        elif kind == "error":
            st.error(message)
        else:
            st.info(message)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
            :root {
                --ucsi-red: #bf1111;
                --ucsi-red-dark: #8f0708;
                --ucsi-red-bright: #e3262e;
                --ucsi-orange: #ff8a34;
                --ucsi-bg: #f6f7fb;
                --ucsi-card: #ffffff;
                --ucsi-text: #212121;
                --ucsi-muted: #7a7a86;
                --ucsi-line: #ececf3;
                --ucsi-green: #1aa05b;
            }

            .stApp {
                background:
                    radial-gradient(circle at top right, rgba(255, 138, 52, 0.22), transparent 22%),
                    linear-gradient(180deg, #f8f8fb 0%, #f2f4f8 100%);
                color: var(--ucsi-text);
            }

            .block-container {
                max-width: 1120px;
                padding-top: 1.2rem;
                padding-bottom: 2.5rem;
            }

            div[data-testid="stSidebar"] {
                background: linear-gradient(180deg, #fffefe 0%, #f5f5f8 100%);
                border-right: 1px solid rgba(200, 200, 215, 0.55);
            }

            .phone-shell {
                width: min(100%, 500px);
                margin: 0 auto 1rem auto;
                background: white;
                border-radius: 34px;
                box-shadow: 0 25px 80px rgba(20, 24, 38, 0.12);
                overflow: hidden;
                border: 1px solid rgba(235, 235, 245, 0.8);
            }

            .hero {
                position: relative;
                padding: 1.3rem 1.4rem 1.35rem 1.4rem;
                color: white;
                background:
                    radial-gradient(circle at top right, rgba(255, 172, 113, 0.92), transparent 18%),
                    radial-gradient(circle at top left, rgba(227, 38, 46, 0.65), transparent 28%),
                    linear-gradient(135deg, var(--ucsi-red-bright) 0%, var(--ucsi-red-dark) 75%);
            }

            .hero::after {
                display: none;
            }

            .hero-top {
                position: relative;
                z-index: 1;
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1.1rem;
            }

            .hero-label {
                position: relative;
                z-index: 1;
                font-size: 1.2rem;
                font-weight: 800;
                letter-spacing: 0.01em;
            }

            .hero-balance {
                position: relative;
                z-index: 1;
                margin-top: 0.15rem;
                font-size: 2.3rem;
                line-height: 1.1;
                font-weight: 900;
            }

            .hero-sub {
                position: relative;
                z-index: 1;
                margin-top: 0.35rem;
                color: rgba(255, 255, 255, 0.88);
                font-size: 0.92rem;
            }

            .hero-badge {
                width: 52px;
                height: 52px;
                border-radius: 999px;
                border: 2px solid rgba(255, 255, 255, 0.78);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.2rem;
                background: rgba(255, 255, 255, 0.08);
            }

            .content {
                position: relative;
                z-index: 2;
                padding: 0.7rem 1.2rem 1.3rem 1.2rem;
            }

            .wallet-glance-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.7rem;
            }

            .wallet-glance-card {
                border-radius: 18px;
                background: linear-gradient(180deg, #fff8f8 0%, #ffffff 100%);
                border: 1px solid #f1d6d6;
                padding: 0.85rem 0.9rem;
            }

            .wallet-glance-label {
                color: var(--ucsi-muted);
                font-size: 0.78rem;
                margin-bottom: 0.2rem;
            }

            .wallet-glance-value {
                color: var(--ucsi-text);
                font-size: 0.94rem;
                font-weight: 800;
            }

            .section-card {
                background: var(--ucsi-card);
                border: 1px solid var(--ucsi-line);
                border-radius: 24px;
                padding: 1rem 1rem 0.9rem 1rem;
                box-shadow: 0 14px 34px rgba(19, 21, 32, 0.05);
                margin-bottom: 1rem;
            }

            .mini-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.6rem;
                text-align: center;
                margin-top: 0.35rem;
            }

            .mini-action {
                border-radius: 18px;
                background: #fff8f8;
                border: 1px solid #f3d7d7;
                padding: 0.7rem 0.45rem;
            }

            .mini-icon {
                font-size: 1.45rem;
                line-height: 1;
                margin-bottom: 0.35rem;
            }

            .mini-label {
                color: var(--ucsi-text);
                font-weight: 700;
                font-size: 0.82rem;
            }

            .section-title {
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-size: 1.02rem;
                font-weight: 800;
                margin-bottom: 0.8rem;
            }

            .section-title span {
                color: var(--ucsi-muted);
                font-size: 0.85rem;
                font-weight: 600;
            }

            .tx-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 0.85rem;
                padding: 0.8rem 0;
                border-bottom: 1px solid var(--ucsi-line);
            }

            .tx-item:last-child {
                border-bottom: none;
                padding-bottom: 0;
            }

            .tx-title {
                font-weight: 800;
                margin-bottom: 0.14rem;
            }

            .tx-meta {
                color: var(--ucsi-muted);
                font-size: 0.83rem;
            }

            .amount-positive {
                color: var(--ucsi-green);
                font-weight: 900;
                white-space: nowrap;
            }

            .amount-negative {
                color: var(--ucsi-red-bright);
                font-weight: 900;
                white-space: nowrap;
            }

            .amount-neutral {
                color: var(--ucsi-muted);
                font-weight: 800;
                white-space: nowrap;
            }

            .login-shell {
                width: min(100%, 500px);
                margin: 0 auto;
                background: white;
                border-radius: 34px;
                overflow: hidden;
                box-shadow: 0 25px 80px rgba(20, 24, 38, 0.12);
                border: 1px solid rgba(235, 235, 245, 0.8);
            }

            .login-wave {
                min-height: 170px;
                background:
                    radial-gradient(circle at top right, rgba(255, 172, 113, 0.96), transparent 17%),
                    radial-gradient(circle at left, rgba(227, 38, 46, 0.78), transparent 32%),
                    linear-gradient(135deg, #db1e21 0%, #9b090a 76%);
                position: relative;
            }

            .login-wave::after {
                display: none;
            }

            .login-body {
                position: relative;
                z-index: 2;
                margin-top: 0;
                padding: 1.75rem 1.5rem 1.5rem 1.5rem;
            }

            .login-title {
                font-size: 2rem;
                font-weight: 900;
                line-height: 1.05;
                margin-bottom: 0.35rem;
            }

            .login-sub {
                color: var(--ucsi-muted);
                margin-bottom: 1rem;
            }

            .demo-pill {
                display: inline-block;
                margin-top: 0.2rem;
                padding: 0.45rem 0.8rem;
                background: #fff3f3;
                border: 1px solid #f7d6d6;
                border-radius: 999px;
                color: #8b0a0d;
                font-size: 0.84rem;
                font-weight: 700;
            }

            .portal-section-title {
                font-size: 1.1rem;
                font-weight: 900;
                color: var(--ucsi-text);
                margin-bottom: 0.4rem;
            }

            .field-title {
                color: var(--ucsi-text);
                font-weight: 700;
                margin-bottom: 0.3rem;
            }

            .admin-kpis {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.8rem;
                margin-bottom: 1rem;
            }

            .kpi-card {
                background: linear-gradient(180deg, #ffffff 0%, #fbfbfd 100%);
                border-radius: 20px;
                border: 1px solid var(--ucsi-line);
                padding: 0.95rem 1rem;
            }

            .kpi-label {
                color: var(--ucsi-muted);
                font-size: 0.83rem;
                font-weight: 700;
                margin-bottom: 0.25rem;
            }

            .kpi-value {
                font-size: 1.5rem;
                font-weight: 900;
            }

            .stButton button {
                border-radius: 999px;
                border: 1px solid #e5c4c4;
                font-weight: 800;
                min-height: 2.85rem;
                background: #fff8f8;
                color: #851014;
            }

            .stFormSubmitButton > button {
                border-radius: 999px;
                border: 1px solid #bf1111;
                font-weight: 800;
                min-height: 2.85rem;
                background: linear-gradient(135deg, #db1e21 0%, #9b090a 100%);
                color: #ffffff;
            }

            .stButton button:hover {
                border-color: #bf1111;
                color: #ffffff;
                background: linear-gradient(135deg, #db1e21 0%, #9b090a 100%);
            }

            .stFormSubmitButton > button:hover {
                border-color: #8f0708;
                color: #ffffff;
                background: linear-gradient(135deg, #c81519 0%, #860607 100%);
            }

            .stButton button:focus {
                color: #851014;
                border-color: #bf1111;
                box-shadow: 0 0 0 0.15rem rgba(191, 17, 17, 0.15);
            }

            .stFormSubmitButton > button:focus {
                color: #ffffff;
                border-color: #bf1111;
                box-shadow: 0 0 0 0.15rem rgba(191, 17, 17, 0.15);
            }

            .quick-action-wrap {
                background: var(--ucsi-card);
                border: 1px solid var(--ucsi-line);
                border-radius: 24px;
                padding: 1rem 1rem 0.9rem 1rem;
                box-shadow: 0 14px 34px rgba(19, 21, 32, 0.05);
                margin-bottom: 1rem;
            }

            .quick-caption {
                color: var(--ucsi-muted);
                font-size: 0.83rem;
                margin-top: 0.55rem;
            }

            .phone-history-card {
                background: var(--ucsi-card);
                border: 1px solid var(--ucsi-line);
                border-radius: 24px;
                padding: 1rem 1rem 0.9rem 1rem;
                box-shadow: 0 14px 34px rgba(19, 21, 32, 0.05);
                margin-bottom: 1rem;
            }

            .summary-card {
                background: var(--ucsi-card);
                border: 1px solid var(--ucsi-line);
                border-radius: 24px;
                padding: 1rem 1rem 0.9rem 1rem;
                box-shadow: 0 14px 34px rgba(19, 21, 32, 0.05);
                margin-bottom: 1rem;
            }

            .summary-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.8rem;
            }

            .two-col-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .summary-item {
                border-radius: 18px;
                background: #fff8f8;
                border: 1px solid #f3d7d7;
                padding: 0.8rem;
            }

            .summary-label {
                color: var(--ucsi-muted);
                font-size: 0.8rem;
                margin-bottom: 0.2rem;
            }

            .summary-value {
                color: var(--ucsi-text);
                font-weight: 800;
                font-size: 0.98rem;
            }

            div[data-testid="stMetric"] {
                background: linear-gradient(180deg, #ffffff 0%, #fbfbfd 100%);
                border: 1px solid var(--ucsi-line);
                border-radius: 20px;
                padding: 0.9rem 1rem;
            }

            div[data-testid="stMetric"] label,
            div[data-testid="stMetric"] div[data-testid="stMetricLabel"],
            div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
                color: var(--ucsi-text) !important;
            }

            .stTextInput input,
            .stNumberInput input,
            .stSelectbox div[data-baseweb="select"] > div,
            .stTextArea textarea {
                border-radius: 16px !important;
            }

            .stSelectbox div[data-baseweb="select"] > div,
            .stSelectbox div[data-baseweb="select"] span,
            .stSelectbox svg {
                color: var(--ucsi-text) !important;
                fill: var(--ucsi-text) !important;
            }

            .stSelectbox div[data-baseweb="select"] > div {
                background-color: #ffffff !important;
                border: 1px solid #d8dbe5 !important;
            }

            .stSelectbox [data-baseweb="select"] input::placeholder,
            .stSelectbox [data-baseweb="select"] [aria-live="polite"] {
                color: var(--ucsi-text) !important;
            }

            .stSelectbox label,
            .stTextInput label,
            .stNumberInput label,
            .stTextArea label,
            .stRadio label,
            .stCaption,
            .stMarkdown,
            .stMarkdown p {
                color: var(--ucsi-text) !important;
            }

            .kpi-flex-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.8rem;
                margin: 0.2rem 0 0.9rem 0;
            }

            .kpi-flex-grid.two-col {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .kpi-flex-card {
                background: linear-gradient(180deg, #ffffff 0%, #fbfbfd 100%);
                border: 1px solid var(--ucsi-line);
                border-radius: 20px;
                padding: 0.95rem 1rem;
                min-height: 96px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                overflow-wrap: anywhere;
                word-break: break-word;
            }

            .kpi-flex-label {
                color: var(--ucsi-muted);
                font-size: 0.83rem;
                font-weight: 700;
                margin-bottom: 0.22rem;
            }

            .kpi-flex-value {
                color: var(--ucsi-text);
                font-size: 1.05rem;
                line-height: 1.25;
                font-weight: 800;
            }

            button[data-baseweb="tab"] {
                color: #61616f !important;
                font-weight: 700 !important;
                border-radius: 999px !important;
                padding: 0.45rem 0.9rem !important;
            }

            button[data-baseweb="tab"][aria-selected="true"] {
                color: var(--ucsi-red-bright) !important;
                background: #fff2f2 !important;
            }

            .custom-alert {
                border-radius: 20px;
                padding: 0.95rem 1rem;
                border: 1px solid #f1db91;
                background: linear-gradient(180deg, #fffaf0 0%, #fff7d9 100%);
                color: #5d4700;
                margin-bottom: 0.8rem;
                box-shadow: 0 10px 25px rgba(20, 24, 38, 0.05);
            }

            .custom-alert.alert-critical {
                border-color: #efb1b1;
                background: linear-gradient(180deg, #fff3f3 0%, #ffe3e3 100%);
                color: #7b0f13;
            }

            .custom-alert-title {
                font-weight: 800;
                margin-bottom: 0.2rem;
            }

            .alert-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 0.75rem;
                margin-bottom: 0.25rem;
            }

            .alert-user {
                font-weight: 700;
                margin-bottom: 0.2rem;
            }

            .alert-time {
                margin-top: 0.35rem;
                font-size: 0.8rem;
                color: inherit;
                opacity: 0.88;
            }

            .severity-badge {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border-radius: 999px;
                padding: 0.2rem 0.55rem;
                font-size: 0.72rem;
                font-weight: 800;
                letter-spacing: 0.02em;
                white-space: nowrap;
            }

            .badge-alert {
                background: #fde6e6;
                color: #961519;
            }

            .badge-warning {
                background: #fff2d7;
                color: #7a5200;
            }

            .badge-success {
                background: #e5f7ed;
                color: #0f7d46;
            }

            .badge-neutral {
                background: #eef0f6;
                color: #4c5566;
            }

            .timeline-shell {
                background: linear-gradient(180deg, #ffffff 0%, #fbfbfd 100%);
                border: 1px solid var(--ucsi-line);
                border-radius: 24px;
                padding: 1rem;
                box-shadow: 0 14px 34px rgba(19, 21, 32, 0.05);
            }

            .timeline-row {
                display: grid;
                grid-template-columns: 18px 1fr;
                gap: 0.8rem;
                padding: 0.8rem 0;
                border-bottom: 1px solid var(--ucsi-line);
            }

            .timeline-row:last-child {
                border-bottom: none;
                padding-bottom: 0;
            }

            .timeline-dot {
                width: 12px;
                height: 12px;
                border-radius: 999px;
                background: linear-gradient(180deg, #db1e21 0%, #9b090a 100%);
                margin-top: 0.35rem;
                box-shadow: 0 0 0 5px rgba(219, 30, 33, 0.08);
            }

            .timeline-top {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 0.8rem;
                margin-bottom: 0.18rem;
            }

            .timeline-right {
                display: flex;
                align-items: center;
                gap: 0.45rem;
            }

            .timeline-title {
                font-weight: 800;
                color: var(--ucsi-text);
            }

            .timeline-meta,
            .timeline-details {
                color: var(--ucsi-muted);
                font-size: 0.83rem;
            }

            .timeline-value {
                color: var(--ucsi-text);
                font-weight: 800;
                white-space: nowrap;
            }

            @media (max-width: 900px) {
                .admin-kpis {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }

                .kpi-flex-grid,
                .kpi-flex-grid.two-col {
                    grid-template-columns: 1fr;
                }

                .wallet-glance-grid,
                .summary-grid,
                .two-col-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    st.session_state.setdefault("portal", "User Portal")
    st.session_state.setdefault("user_id", None)
    st.session_state.setdefault("user_phone_input", "+60123456789")
    st.session_state.setdefault("user_pin_input", "1234")
    st.session_state.setdefault("user_view", "Dashboard")
    st.session_state.setdefault("pending_topup_amount", None)
    st.session_state.setdefault("pending_topup_method", "Debit/Credit Card")
    st.session_state.setdefault("flash_messages", [])


def init_db() -> None:
    connection = get_connection()
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            campus_id TEXT NOT NULL UNIQUE,
            card_id TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL UNIQUE,
            pin TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0,
            role TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            location TEXT,
            amount REAL NOT NULL,
            balance_after REAL NOT NULL,
            timestamp TEXT NOT NULL,
            details TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS parking_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            entry_time TEXT NOT NULL,
            exit_time TEXT,
            duration_minutes INTEGER,
            fee REAL,
            status TEXT NOT NULL DEFAULT 'OPEN',
            entry_location TEXT,
            exit_location TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'INFO',
            location TEXT,
            details TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """
    )
    user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 0:
        seed_demo_data(connection)
    connection.commit()
    connection.close()


def student_names() -> list[str]:
    return [
        "Aiman Iskandar", "Nur Aisyah", "Tan Wei Jie", "Lee Jia Xin", "Raj Kumar",
        "Anjali Devi", "Muhammad Danish", "Siti Hajar", "Lim Zi Xuan", "Ng Yu Wen",
        "Arun Prakash", "Harpreet Kaur", "Farah Nabila", "Irfan Hakim", "Teh Wen Qi",
        "Chong Kai Ting", "Sharvin Raj", "Nisha Kumari", "Haziq Azman", "Amirul Syafiq",
        "Chew Xin Yi", "Low Jia Hao", "Kavin Ramasamy", "Pavithra Nair", "John Matthew",
        "Sarah Wong", "Nurul Iman", "Yap Hui Ling", "Gan Yew Soon", "Daniel Lee",
        "Zarina Binti Omar", "Aqilah Sofea", "Bryan Teo", "Nicole Tan", "Shivani Menon",
        "Marcus Lim", "Puteri Balqis", "Faizal Rahman", "Melissa Chai", "Zulhilmi Shah",
    ]


def staff_names() -> list[str]:
    return [
        "Dr. Faridah Hassan", "Ms. Cheryl Tan", "Mr. Arvind Rao", "Dr. Kavitha Nair",
        "Mr. Samuel Loh", "Ms. Nur Sabrina", "Mr. Daniel Wong", "Dr. Priya Shankar",
        "Ms. Lim Siew Ling", "Mr. Hafiz Roslan",
    ]


def make_phone(index: int) -> str:
    return f"+6011{index:08d}"


def parking_fee(hours: float) -> float:
    if hours <= 3:
        return 3.0
    if hours <= 4:
        return 4.0
    if hours <= 5:
        return 5.0
    return 6.0


def calculate_exit_fee(entry_time: datetime, exit_time: datetime, entry_gate: str, exit_gate: str) -> tuple[float, str]:
    duration_minutes = max(0, int((exit_time - entry_time).total_seconds() // 60))
    same_gate = entry_gate == exit_gate

    if duration_minutes <= 15:
        if same_gate:
            return 0.0, f"Grace exit: {duration_minutes} minutes at the same gate."
        return 1.0, f"Cross-gate exit within 15 minutes: {duration_minutes} minutes."

    duration_hours = duration_minutes / 60
    fee = parking_fee(duration_hours)
    return fee, f"Standard parking fee for {duration_minutes} minutes."


def insert_transaction(
    connection: sqlite3.Connection,
    user_id: int,
    tx_type: str,
    amount: float,
    balance_after: float,
    timestamp: datetime,
    location: str = "",
    details: str = "",
) -> None:
    connection.execute(
        """
        INSERT INTO transactions (user_id, type, location, amount, balance_after, timestamp, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            tx_type,
            location,
            round(amount, 2),
            round(balance_after, 2),
            timestamp.isoformat(sep=" "),
            details,
        ),
    )


def insert_audit_event(
    connection: sqlite3.Connection,
    event_type: str,
    severity: str,
    timestamp: datetime,
    user_id: int | None = None,
    location: str = "",
    details: str = "",
) -> None:
    connection.execute(
        """
        INSERT INTO audit_events (user_id, event_type, severity, location, details, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            event_type,
            severity,
            location,
            details,
            timestamp.isoformat(sep=" "),
        ),
    )


def seed_demo_data(connection: sqlite3.Connection) -> None:
    rng = random.Random(42)

    users: list[tuple[str, str, str, str, str, float, str]] = []

    users.append(
        (
            "Test Student",
            "1002456789",
            "NFC-UCSI-0001",
            "+60123456789",
            "1234",
            20.0,
            "student",
        )
    )

    for index, name in enumerate(student_names()[1:], start=2):
        year = 20 + ((index - 2) % 6)
        campus_id = f"100{year:02d}{rng.randint(10000, 99999)}"
        card_id = f"NFC-UCSI-{index:04d}"
        phone = make_phone(index)
        balance = round(rng.uniform(12, 180), 2)
        users.append((name, campus_id, card_id, phone, "1234", balance, "student"))

    for offset, name in enumerate(staff_names(), start=41):
        campus_id = f"100{offset:02d}"
        card_id = f"NFC-UCSI-{offset:04d}"
        phone = make_phone(offset)
        balance = round(rng.uniform(60, 180), 2)
        users.append((name, campus_id, card_id, phone, "1234", balance, "staff"))

    connection.executemany(
        """
        INSERT INTO users (name, campus_id, card_id, phone, pin, balance, role)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        users,
    )

    inserted_users = connection.execute(
        "SELECT id, name, role, balance FROM users ORDER BY id"
    ).fetchall()

    current_balances = {row["id"]: row["balance"] for row in inserted_users}
    base_time = now_local() - timedelta(days=35)

    for row in inserted_users:
        user_id = row["id"]
        event_time = base_time + timedelta(hours=user_id)

        if user_id == 1:
            current_balances[user_id] = 50.0
            insert_transaction(
                connection,
                user_id,
                "TOP_UP",
                20.0,
                40.0,
                event_time,
                "Reload kiosk",
                "Seeded demo top up",
            )
            current_balances[user_id] = 40.0
            insert_transaction(
                connection,
                user_id,
                "PAYMENT",
                -3.0,
                37.0,
                event_time + timedelta(days=1, hours=1),
                "Library Cafe",
                "Lunch purchase",
            )
            insert_transaction(
                connection,
                user_id,
                "TOP_UP",
                15.0,
                52.0,
                event_time + timedelta(days=2, hours=3),
                "Reload kiosk",
                "Wallet reload",
            )
            insert_transaction(
                connection,
                user_id,
                "PAYMENT",
                -2.0,
                50.0,
                event_time + timedelta(days=3, hours=2),
                "Campus Mart",
                "Snack purchase",
            )
            current_balances[user_id] = 50.0
            continue

        sample_count = rng.randint(1, 3)
        for _ in range(sample_count):
            tx_kind = rng.choice(["TOP_UP", "PAYMENT"])
            event_time += timedelta(hours=rng.randint(10, 40))

            if tx_kind == "TOP_UP":
                amount = float(rng.choice([10, 25, 50]))
                next_balance = min(MAX_WALLET_BALANCE, current_balances[user_id] + amount)
                amount = round(next_balance - current_balances[user_id], 2)
                if amount <= 0:
                    continue
                current_balances[user_id] = next_balance
                insert_transaction(
                    connection,
                    user_id,
                    "TOP_UP",
                    amount,
                    current_balances[user_id],
                    event_time,
                    "Reload kiosk",
                    "Seeded reload",
                )
            else:
                amount = round(min(current_balances[user_id], rng.uniform(2, 8)), 2)
                if amount <= 0:
                    continue
                current_balances[user_id] = round(current_balances[user_id] - amount, 2)
                insert_transaction(
                    connection,
                    user_id,
                    "PAYMENT",
                    -amount,
                    current_balances[user_id],
                    event_time,
                    rng.choice(PAYMENT_LOCATIONS),
                    "Seeded merchant payment",
                )

        connection.execute(
            "UPDATE users SET balance = ? WHERE id = ?",
            (round(current_balances[user_id], 2), user_id),
        )


def authenticate(phone: str, pin: str) -> sqlite3.Row | None:
    connection = get_connection()
    user = connection.execute(
        "SELECT * FROM users WHERE phone = ? AND pin = ?",
        (phone.strip(), pin.strip()),
    ).fetchone()
    connection.close()
    return user


def fetch_user(user_id: int) -> sqlite3.Row | None:
    connection = get_connection()
    user = connection.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    connection.close()
    return user


def list_users() -> list[sqlite3.Row]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT * FROM users ORDER BY role, name"
    ).fetchall()
    connection.close()
    return rows


def recent_transactions(user_id: int, limit: int | None = None) -> list[sqlite3.Row]:
    connection = get_connection()
    query = """
        SELECT * FROM transactions
        WHERE user_id = ?
        ORDER BY datetime(timestamp) DESC, id DESC
    """
    params: list[object] = [user_id]
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    rows = connection.execute(query, params).fetchall()
    connection.close()
    return rows


def all_transactions(limit: int = 120) -> list[sqlite3.Row]:
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT t.*, u.name, u.card_id
        FROM transactions t
        JOIN users u ON u.id = t.user_id
        ORDER BY datetime(t.timestamp) DESC, t.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    connection.close()
    return rows


def open_parking_session(user_id: int) -> sqlite3.Row | None:
    connection = get_connection()
    row = connection.execute(
        """
        SELECT * FROM parking_sessions
        WHERE user_id = ? AND status = 'OPEN'
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    connection.close()
    return row


def open_parking_count() -> int:
    connection = get_connection()
    count = connection.execute(
        "SELECT COUNT(*) FROM parking_sessions WHERE status = 'OPEN'"
    ).fetchone()[0]
    connection.close()
    return int(count)


def wallet_total() -> float:
    connection = get_connection()
    total = connection.execute("SELECT COALESCE(SUM(balance), 0) FROM users").fetchone()[0]
    connection.close()
    return float(total or 0)


def user_count() -> int:
    connection = get_connection()
    count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    connection.close()
    return int(count)


def gate_activity_snapshot() -> list[dict[str, object]]:
    connection = get_connection()
    rows = []
    for gate in GATE_LOCATIONS:
        entries = connection.execute(
            "SELECT COUNT(*) FROM parking_sessions WHERE entry_location = ?",
            (gate,),
        ).fetchone()[0]
        exits = connection.execute(
            "SELECT COUNT(*) FROM parking_sessions WHERE exit_location = ?",
            (gate,),
        ).fetchone()[0]
        rows.append({"gate": gate, "entries": int(entries), "exits": int(exits)})
    connection.close()
    return rows


def audit_summary() -> dict[str, int]:
    connection = get_connection()
    cross_gate_quick = connection.execute(
        """
        SELECT COUNT(*)
        FROM parking_sessions
        WHERE status = 'CLOSED'
          AND duration_minutes IS NOT NULL
          AND duration_minutes <= 15
          AND COALESCE(entry_location, '') <> COALESCE(exit_location, '')
        """
    ).fetchone()[0]
    free_same_gate = connection.execute(
        """
        SELECT COUNT(*)
        FROM parking_sessions
        WHERE status = 'CLOSED'
          AND duration_minutes IS NOT NULL
          AND duration_minutes <= 15
          AND COALESCE(entry_location, '') = COALESCE(exit_location, '')
        """
    ).fetchone()[0]
    low_balance = connection.execute(
        "SELECT COUNT(*) FROM users WHERE balance < 5"
    ).fetchone()[0]
    connection.close()
    return {
        "cross_gate_quick": int(cross_gate_quick),
        "free_same_gate": int(free_same_gate),
        "low_balance": int(low_balance),
    }


def suspicious_access_alerts(limit: int = 10) -> list[dict[str, object]]:
    connection = get_connection()
    alerts: list[dict[str, object]] = []

    repeated_cross_gate = connection.execute(
        """
        SELECT ae.user_id, u.name, COUNT(*) AS event_count, MAX(ae.timestamp) AS last_seen
        FROM audit_events ae
        JOIN users u ON u.id = ae.user_id
        WHERE ae.event_type = 'CROSS_GATE_QUICK_EXIT'
        GROUP BY ae.user_id, u.name
        HAVING COUNT(*) >= 2
        ORDER BY last_seen DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    for row in repeated_cross_gate:
        alerts.append(
            {
                "severity": "ALERT",
                "title": "Repeated short cross-gate exits",
                "user_id": row["user_id"],
                "user_name": row["name"],
                "details": f"{row['event_count']} suspicious short exits across different gates.",
                "timestamp": row["last_seen"],
            }
        )

    failed_taps = connection.execute(
        """
        SELECT ae.user_id, u.name, COUNT(*) AS event_count, MAX(ae.timestamp) AS last_seen
        FROM audit_events ae
        JOIN users u ON u.id = ae.user_id
        WHERE ae.event_type IN ('EXIT_DENIED', 'PAYMENT_DENIED', 'ENTRY_DENIED')
        GROUP BY ae.user_id, u.name
        HAVING COUNT(*) >= 2
        ORDER BY last_seen DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    for row in failed_taps:
        alerts.append(
            {
                "severity": "WARNING",
                "title": "Repeated failed taps",
                "user_id": row["user_id"],
                "user_name": row["name"],
                "details": f"{row['event_count']} denied actions were recorded.",
                "timestamp": row["last_seen"],
            }
        )

    connection.close()
    alerts.sort(key=lambda item: item["timestamp"], reverse=True)
    return alerts[:limit]


def failed_tap_history(limit: int = 8) -> list[dict[str, object]]:
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT ae.timestamp, u.name, u.card_id, ae.event_type, ae.location, ae.details
        FROM audit_events ae
        JOIN users u ON u.id = ae.user_id
        WHERE ae.event_type IN ('ENTRY_DENIED', 'EXIT_DENIED', 'PAYMENT_DENIED', 'TOP_UP_DENIED')
        ORDER BY datetime(ae.timestamp) DESC, ae.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    connection.close()
    return [
        {
            "time": fmt_dt(row["timestamp"]),
            "user": row["name"],
            "card_id": row["card_id"],
            "event": row["event_type"].replace("_", " ").title(),
            "location": row["location"] or "-",
            "details": row["details"] or "-",
        }
        for row in rows
    ]


def merchant_usage_snapshot() -> list[dict[str, object]]:
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT location, COUNT(*) AS tx_count, ROUND(SUM(ABS(amount)), 2) AS total_spend
        FROM transactions
        WHERE type = 'PAYMENT'
        GROUP BY location
        ORDER BY tx_count DESC, total_spend DESC
        """
    ).fetchall()
    connection.close()
    return [
        {
            "merchant": row["location"] or "Campus merchant",
            "transactions": int(row["tx_count"]),
            "total_spend": float(row["total_spend"] or 0),
        }
        for row in rows
    ]


def demo_account_directory() -> list[dict[str, object]]:
    return [
        {
            "name": row["name"],
            "phone": row["phone"],
            "role": row["role"].title(),
            "balance": fmt_balance(row["balance"]),
            "card_id": row["card_id"],
        }
        for row in list_users()
    ]


def user_unified_view(user_id: int) -> dict[str, object] | None:
    user = fetch_user(user_id)
    if not user:
        return None

    active_session = open_parking_session(user_id)
    transactions = recent_transactions(user_id, limit=12)
    connection = get_connection()
    audit_events = connection.execute(
        """
        SELECT *
        FROM audit_events
        WHERE user_id = ?
        ORDER BY datetime(timestamp) DESC, id DESC
        LIMIT 12
        """,
        (user_id,),
    ).fetchall()
    connection.close()

    timeline: list[dict[str, object]] = []
    for tx in transactions:
        severity = "SUCCESS" if tx["amount"] >= 0 else "INFO"
        timeline.append(
            {
                "timestamp": tx["timestamp"],
                "kind": "transaction",
                "title": action_label(tx["type"]),
                "details": tx["details"] or tx["location"] or "",
                "value": fmt_money(tx["amount"]),
                "severity": severity,
            }
        )
    for event in audit_events:
        timeline.append(
            {
                "timestamp": event["timestamp"],
                "kind": "audit",
                "title": event["event_type"].replace("_", " ").title(),
                "details": event["details"] or event["location"] or "",
                "value": event["severity"],
                "severity": event["severity"],
            }
        )

    timeline.sort(key=lambda item: item["timestamp"], reverse=True)
    return {
        "user": user,
        "active_session": active_session,
        "timeline": timeline[:14],
    }


def top_up_wallet(user_id: int, amount: float, location: str, tx_type: str) -> tuple[bool, str]:
    if amount < MIN_TOP_UP:
        return False, f"Minimum top up is {fmt_money(MIN_TOP_UP)}."

    connection = get_connection()
    user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        connection.close()
        return False, "User not found."

    new_balance = round(user["balance"] + amount, 2)
    if new_balance > MAX_WALLET_BALANCE:
        insert_audit_event(
            connection,
            event_type="TOP_UP_DENIED",
            severity="WARNING",
            timestamp=now_local(),
            user_id=user_id,
            location=location,
            details=f"Top up denied because wallet cap would exceed {fmt_money(MAX_WALLET_BALANCE)}.",
        )
        connection.commit()
        connection.close()
        return False, f"Wallet cap is {fmt_money(MAX_WALLET_BALANCE)}."

    timestamp = now_local()
    connection.execute(
        "UPDATE users SET balance = ? WHERE id = ?",
        (new_balance, user_id),
    )
    insert_transaction(
        connection,
        user_id,
        tx_type,
        amount,
        new_balance,
        timestamp,
        location,
        "Wallet reload",
    )
    insert_audit_event(
        connection,
        event_type="TOP_UP_SUCCESS",
        severity="INFO",
        timestamp=timestamp,
        user_id=user_id,
        location=location,
        details=f"Top up completed: {fmt_money(amount)}.",
    )
    connection.commit()
    connection.close()
    return True, f"Top up successful. New balance: {fmt_balance(new_balance)}."


def make_payment(user_id: int, amount: float, location: str) -> tuple[bool, str]:
    if amount <= 0:
        return False, "Payment amount must be greater than zero."

    connection = get_connection()
    user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        connection.close()
        return False, "User not found."

    if user["balance"] < amount:
        insert_audit_event(
            connection,
            event_type="PAYMENT_DENIED",
            severity="WARNING",
            timestamp=now_local(),
            user_id=user_id,
            location=location,
            details=f"Payment denied for {fmt_money(amount)} due to insufficient balance.",
        )
        connection.commit()
        connection.close()
        return False, "Insufficient balance for this payment."

    new_balance = round(user["balance"] - amount, 2)
    timestamp = now_local()
    connection.execute(
        "UPDATE users SET balance = ? WHERE id = ?",
        (new_balance, user_id),
    )
    insert_transaction(
        connection,
        user_id,
        "PAYMENT",
        -amount,
        new_balance,
        timestamp,
        location or "Campus merchant",
        "Cashless payment",
    )
    insert_audit_event(
        connection,
        event_type="PAYMENT_SUCCESS",
        severity="INFO",
        timestamp=timestamp,
        user_id=user_id,
        location=location,
        details=f"Payment completed: {fmt_money(amount)} at {location or 'Campus merchant'}.",
    )
    connection.commit()
    connection.close()
    return True, f"Payment approved. New balance: {fmt_balance(new_balance)}."


def parking_entry(user_id: int, location: str) -> tuple[bool, str]:
    connection = get_connection()
    timestamp = now_local()
    existing = connection.execute(
        """
        SELECT id FROM parking_sessions
        WHERE user_id = ? AND status = 'OPEN'
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    if existing:
        insert_audit_event(
            connection,
            event_type="ENTRY_DENIED",
            severity="WARNING",
            timestamp=timestamp,
            user_id=user_id,
            location=location,
            details="Entry denied because the user already has an open parking session.",
        )
        connection.commit()
        connection.close()
        return False, "This user already has an active parking session."

    user = connection.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        connection.close()
        return False, "User not found."

    connection.execute(
        """
        INSERT INTO parking_sessions (user_id, entry_time, status, entry_location)
        VALUES (?, ?, 'OPEN', ?)
        """,
        (user_id, timestamp.isoformat(sep=" "), location),
    )
    insert_transaction(
        connection,
        user_id,
        "PARKING_ENTRY",
        0.0,
        user["balance"],
        timestamp,
        location,
        "NFC entry tap",
    )
    insert_audit_event(
        connection,
        event_type="ENTRY_SUCCESS",
        severity="INFO",
        timestamp=timestamp,
        user_id=user_id,
        location=location,
        details=f"Vehicle entry approved at {location}.",
    )
    connection.commit()
    connection.close()
    return True, f"Entry recorded at {location or 'campus gate'}."


def parking_exit(user_id: int, location: str) -> tuple[bool, str]:
    connection = get_connection()
    user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    session = connection.execute(
        """
        SELECT * FROM parking_sessions
        WHERE user_id = ? AND status = 'OPEN'
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    if not user or not session:
        insert_audit_event(
            connection,
            event_type="EXIT_DENIED",
            severity="WARNING",
            timestamp=now_local(),
            user_id=user_id,
            location=location,
            details="Exit denied because no active parking session was found.",
        )
        connection.commit()
        connection.close()
        return False, "No active parking session found for this user."

    entry_time = datetime.fromisoformat(session["entry_time"])
    exit_time = now_local()
    fee, fee_reason = calculate_exit_fee(
        entry_time=entry_time,
        exit_time=exit_time,
        entry_gate=session["entry_location"] or "",
        exit_gate=location or "",
    )
    duration_minutes = max(0, int((exit_time - entry_time).total_seconds() // 60))

    if user["balance"] < fee:
        insert_audit_event(
            connection,
            event_type="EXIT_DENIED",
            severity="WARNING",
            timestamp=exit_time,
            user_id=user_id,
            location=location,
            details=f"Exit denied due to insufficient balance. Required fee: {fmt_money(fee)}.",
        )
        connection.commit()
        connection.close()
        return False, f"Insufficient balance. Exit fee is {fmt_money(fee)}."

    new_balance = round(user["balance"] - fee, 2)

    connection.execute(
        "UPDATE users SET balance = ? WHERE id = ?",
        (new_balance, user_id),
    )
    connection.execute(
        """
        UPDATE parking_sessions
        SET exit_time = ?, duration_minutes = ?, fee = ?, status = 'CLOSED', exit_location = ?
        WHERE id = ?
        """,
        (
            exit_time.isoformat(sep=" "),
            duration_minutes,
            fee,
            location,
            session["id"],
        ),
    )
    insert_transaction(
        connection,
        user_id,
        "PARKING_EXIT",
        -fee,
        new_balance,
        exit_time,
        location or "Campus exit",
        (
            f"{fee_reason} "
            f"Entry gate: {session['entry_location'] or '-'} | Exit gate: {location or '-'} | "
            f"Duration: {duration_minutes} minutes"
        ),
    )
    severity = "INFO"
    event_type = "EXIT_SUCCESS"
    if duration_minutes <= 15 and (session["entry_location"] or "") != (location or ""):
        severity = "ALERT"
        event_type = "CROSS_GATE_QUICK_EXIT"
    insert_audit_event(
        connection,
        event_type=event_type,
        severity=severity,
        timestamp=exit_time,
        user_id=user_id,
        location=location,
        details=(
            f"{fee_reason} Entry gate: {session['entry_location'] or '-'} | "
            f"Exit gate: {location or '-'} | Duration: {duration_minutes} minutes"
        ),
    )
    connection.commit()
    connection.close()

    duration_text = f"{duration_minutes} minutes"
    return True, (
        f"Exit approved. Duration: {duration_text}, fee: {fmt_money(fee)}, "
        f"new balance: {fmt_balance(new_balance)}."
    )


def render_user_transaction_list(transactions: list[sqlite3.Row]) -> None:
    if not transactions:
        st.info("No transactions yet.")
        return

    items = []
    for tx in transactions:
        location = tx["location"] or "Campus service"
        details = tx["details"] or location
        items.append(
            f"""
            <div class="tx-item">
                <div>
                    <div class="tx-title">{action_label(tx["type"])}</div>
                    <div class="tx-meta">{location} • {fmt_dt(tx["timestamp"])}</div>
                    <div class="tx-meta">{details}</div>
                </div>
                <div class="{amount_class(tx["amount"])}">{fmt_money(tx["amount"])}</div>
            </div>
            """
        )

    st.markdown("".join(items), unsafe_allow_html=True)


def render_login_portal() -> None:
    st.markdown(
        """
        <div class="login-shell">
            <div class="login-wave"></div>
            <div class="login-body">
                <div class="login-title">Open Your UCSI Pay Wallet</div>
                <div class="login-sub">Use your campus-linked mobile number and PIN to access the demo wallet.</div>
                <div class="demo-pill">Demo login: +60123456789 / 1234</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form", clear_on_submit=False):
        phone = st.text_input("Mobile Number", key="user_phone_input")
        pin = st.text_input("PIN", type="password", key="user_pin_input")
        submitted = st.form_submit_button("Log In", use_container_width=True)

    with st.expander("Browse demo accounts"):
        st.caption("Every seeded user can log in with their phone number and PIN `1234`.")
        st.dataframe(demo_account_directory(), use_container_width=True, hide_index=True)

    if submitted:
        user = authenticate(phone, pin)
        if user:
            st.session_state.user_id = user["id"]
            st.session_state.user_view = "Dashboard"
            push_flash("success", f"Welcome back, {user['name']}.")
            st.rerun()
        else:
            push_flash("error", "Invalid mobile number or PIN.")
            st.rerun()


def render_user_top_up(user: sqlite3.Row) -> None:
    st.markdown('<div class="portal-section-title">Reload Wallet</div>', unsafe_allow_html=True)
    st.caption(f"Minimum reload is {fmt_money(MIN_TOP_UP)} and the wallet cap is {fmt_money(MAX_WALLET_BALANCE)}.")

    payment_method = st.selectbox(
        "Payment method",
        ["Debit/Credit Card", "Online Banking", "E-wallet"],
        key="user_topup_payment_method",
    )

    preset_columns = st.columns(3)
    for index, amount in enumerate(PRESET_TOP_UPS):
        with preset_columns[index % 3]:
            if st.button(f"RM{amount}", key=f"preset_{amount}", use_container_width=True):
                st.session_state.pending_topup_amount = float(amount)
                st.session_state.pending_topup_method = payment_method
                st.rerun()

    custom_amount = st.number_input(
        "Custom top up amount",
        min_value=float(MIN_TOP_UP),
        max_value=float(MAX_WALLET_BALANCE),
        value=25.0,
        step=5.0,
        key="user_custom_topup",
    )
    if st.button("Confirm Reload", key="confirm_user_topup", use_container_width=True):
        st.session_state.pending_topup_amount = float(custom_amount)
        st.session_state.pending_topup_method = payment_method
        st.rerun()

    pending_amount = st.session_state.get("pending_topup_amount")
    if pending_amount:
        st.warning(
            f"Confirm top up of {fmt_money(float(pending_amount))} via {st.session_state.get('pending_topup_method', payment_method)}."
        )
        confirm_cols = st.columns(2)
        if confirm_cols[0].button("Submit Payment", key="submit_topup_payment", use_container_width=True):
            location = f"Self-service reload ({st.session_state.get('pending_topup_method', payment_method)})"
            ok, message = top_up_wallet(user["id"], float(pending_amount), location, "TOP_UP")
            push_flash("success" if ok else "error", message)
            st.session_state.pending_topup_amount = None
            st.rerun()
        if confirm_cols[1].button("Cancel", key="cancel_topup_payment", use_container_width=True):
            st.session_state.pending_topup_amount = None
            push_flash("info", "Top up cancelled.")
            st.rerun()


def render_user_parking(user: sqlite3.Row) -> None:
    st.markdown('<div class="portal-section-title">Parking Status</div>', unsafe_allow_html=True)
    active_session = open_parking_session(user["id"])
    if active_session:
        entry_time = fmt_dt(active_session["entry_time"])
        location = active_session["entry_location"] or "Campus gate"
        st.info(f"Active parking session from {location} since {entry_time}. Exit is recorded in real time from the admin tap simulator.")
    else:
        st.success("No active parking session. The next NFC parking tap can be simulated from the admin portal.")

    parking_rows = [tx for tx in recent_transactions(user["id"], limit=20) if tx["type"] in {"PARKING_ENTRY", "PARKING_EXIT"}]
    st.caption("Recent parking-related activity")
    render_user_transaction_list(parking_rows[:8])


def set_user_view(view: str) -> None:
    st.session_state.user_view = view


def render_phone_shell(user: sqlite3.Row, latest_transactions: list[sqlite3.Row], active_session: sqlite3.Row | None) -> None:
    latest_action = action_label(latest_transactions[0]["type"]) if latest_transactions else "No activity yet"
    parking_status = active_session["entry_location"] if active_session else "No active parking"
    status_label = "Inside campus" if active_session else "Ready to tap"

    st.markdown(
        f"""
        <div class="phone-shell">
            <div class="hero">
                <div class="hero-top">
                    <div>
                        <div class="hero-label">UCSIPAY Balance</div>
                        <div class="hero-balance">{fmt_balance(user["balance"])}</div>
                        <div class="hero-sub">{user["name"]} | {user["role"].title()} | {user["card_id"]}</div>
                    </div>
                    <div class="hero-badge">ID</div>
                </div>
            </div>
            <div class="content">
                <div class="wallet-glance-grid">
                    <div class="wallet-glance-card">
                        <div class="wallet-glance-label">Status</div>
                        <div class="wallet-glance-value">{status_label}</div>
                    </div>
                    <div class="wallet-glance-card">
                        <div class="wallet-glance-label">Parking</div>
                        <div class="wallet-glance-value">{parking_status}</div>
                    </div>
                    <div class="wallet-glance-card">
                        <div class="wallet-glance-label">Latest activity</div>
                        <div class="wallet-glance-value">{latest_action}</div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_user_dashboard(user: sqlite3.Row, latest_transactions: list[sqlite3.Row], active_session: sqlite3.Row | None) -> None:
    left, right = st.columns([1.35, 0.9])
    with left:
        st.markdown(
            """
            <div class="phone-history-card">
                <div class="section-title">Recent Activity <span>Last 5 items</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_user_transaction_list(latest_transactions)

    with right:
        parking_label = active_session["entry_location"] if active_session else "No active session"
        st.markdown(
            f"""
            <div class="summary-card">
                <div class="section-title">Wallet Snapshot <span>Live</span></div>
                <div class="summary-grid two-col-grid">
                    <div class="summary-item">
                        <div class="summary-label">Phone</div>
                        <div class="summary-value">{user["phone"]}</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-label">Role</div>
                        <div class="summary-value">{user["role"].title()}</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-label">Parking</div>
                        <div class="summary-value">{parking_label}</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-label">Campus ID</div>
                        <div class="summary-value">{user["campus_id"]}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_user_portal() -> None:
    user_id = st.session_state.user_id
    if not user_id:
        render_login_portal()
        return

    user = fetch_user(user_id)
    if not user:
        st.session_state.user_id = None
        push_flash("error", "Your session expired. Please log in again.")
        st.rerun()
        return

    latest_transactions = recent_transactions(user["id"], limit=5)
    active_session = open_parking_session(user["id"])
    render_phone_shell(user, latest_transactions, active_session)

    nav_cols = st.columns([1, 1, 1, 1, 0.9])
    if nav_cols[0].button("Dashboard", key="user_nav_dashboard", use_container_width=True):
        set_user_view("Dashboard")
        st.rerun()
    if nav_cols[1].button("Wallet", key="user_nav_wallet", use_container_width=True):
        set_user_view("Top Up")
        st.rerun()
    if nav_cols[2].button("Parking", key="user_nav_parking", use_container_width=True):
        set_user_view("Parking")
        st.rerun()
    if nav_cols[3].button("Activity", key="user_nav_activity", use_container_width=True):
        set_user_view("History")
        st.rerun()
    if nav_cols[4].button("Logout", key="user_nav_logout", use_container_width=True):
        st.session_state.user_id = None
        set_user_view("Dashboard")
        push_flash("info", "You have been logged out.")
        st.rerun()

    st.write("")
    current_view = st.session_state.user_view
    if current_view == "Top Up":
        render_user_top_up(user)
    elif current_view == "Parking":
        render_user_parking(user)
    elif current_view == "History":
        st.markdown('<div class="portal-section-title">Activity History</div>', unsafe_allow_html=True)
        render_user_transaction_list(recent_transactions(user["id"]))
    else:
        render_user_dashboard(user, latest_transactions, active_session)


def render_alert_list(alerts: list[dict[str, object]]) -> None:
    if not alerts:
        st.success("No suspicious access alerts right now.")
        return

    for alert in alerts:
        severity_class = "badge-alert" if alert["severity"] == "ALERT" else "badge-warning"
        alert_class = "alert-critical" if alert["severity"] == "ALERT" else ""
        st.markdown(
            f"""
            <div class="custom-alert {alert_class}">
                <div class="alert-row">
                    <div class="custom-alert-title">{alert['title']}</div>
                    <div class="severity-badge {severity_class}">{alert['severity']}</div>
                </div>
                <div class="alert-user">{alert['user_name']}</div>
                <div>{alert['details']}</div>
                <div class="alert-time">{fmt_dt(str(alert['timestamp']))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_failed_tap_table(rows: list[dict[str, object]]) -> None:
    if not rows:
        st.success("No denied taps recorded in the latest audit window.")
        return
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_unified_profile(user_id: int | None) -> None:
    if not user_id:
        st.info("Select a user to open the unified credential view.")
        return

    view = user_unified_view(user_id)
    if not view:
        st.info("User not found.")
        return

    user = view["user"]
    active_session = view["active_session"]
    profile_cards = [
        ("Balance", fmt_balance(user["balance"])),
        ("Role", user["role"].title()),
        ("Card ID", user["card_id"]),
        ("Parking", active_session["entry_location"] if active_session else "Not parked"),
    ]
    profile_cards_html = "".join(
        (
            '<div class="kpi-flex-card">'
            f'<div class="kpi-flex-label">{escape(label)}</div>'
            f'<div class="kpi-flex-value">{escape(value)}</div>'
            "</div>"
        )
        for label, value in profile_cards
    )
    st.markdown(
        f'<div class="kpi-flex-grid">{profile_cards_html}</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"{user['name']} | {user['phone']} | {user['campus_id']}")
    if active_session:
        st.info(
            f"Active parking session: {active_session['entry_location'] or 'Gate'} since "
            f"{fmt_dt(active_session['entry_time'])}"
        )

    timeline_markup = []
    for item in view["timeline"]:
        severity = str(item.get("severity", "INFO"))
        badge_class = {
            "ALERT": "badge-alert",
            "WARNING": "badge-warning",
            "SUCCESS": "badge-success",
        }.get(severity, "badge-neutral")
        kind_label = "Access / Audit" if item["kind"] == "audit" else "Wallet / Parking"
        title_text = escape(str(item["title"]))
        value_text = escape(str(item["value"]))
        details_text = escape(str(item["details"] or "-"))
        timeline_markup.append(
            (
                '<div class="timeline-row">'
                '<div class="timeline-dot"></div>'
                '<div class="timeline-content">'
                '<div class="timeline-top">'
                f'<div class="timeline-title">{title_text}</div>'
                '<div class="timeline-right">'
                f'<div class="severity-badge {badge_class}">{severity}</div>'
                f'<div class="timeline-value">{value_text}</div>'
                "</div>"
                "</div>"
                f'<div class="timeline-meta">{fmt_dt(str(item["timestamp"]))} | {kind_label}</div>'
                f'<div class="timeline-details">{details_text}</div>'
                "</div>"
                "</div>"
            )
        )

    timeline_html = "".join(timeline_markup) if timeline_markup else '<div class="tx-meta">No events available yet.</div>'
    st.markdown(
        (
            '<div class="timeline-shell">'
            '<div class="section-title">Unified Activity Timeline <span>Latest 14 events</span></div>'
            f"{timeline_html}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_visitor_lane_panel() -> None:
    st.markdown('<div class="portal-section-title">Hybrid Access Model</div>', unsafe_allow_html=True)
    st.dataframe(
        [
            {"Lane": "NFC lane", "Audience": "Students / Staff", "Method": "Card tap tied to wallet and access rules"},
            {"Lane": "LPR lane", "Audience": "Visitors", "Method": "External visitor recognition workflow"},
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.info("This prototype demonstrates a hybrid campus model: NFC for students and staff, with visitor processing remaining on the LPR side.")


def render_demo_accounts_panel() -> None:
    st.markdown('<div class="portal-section-title">Demo Account Directory</div>', unsafe_allow_html=True)
    st.caption("All 50 seeded users can access the user portal using their phone number and PIN `1234`.")
    st.dataframe(demo_account_directory(), use_container_width=True, hide_index=True)


def render_chart_kpis(metrics: list[tuple[str, str]]) -> None:
    grid_class = "kpi-flex-grid two-col" if len(metrics) == 2 else "kpi-flex-grid"
    cards_html = "".join(
        (
            '<div class="kpi-flex-card">'
            f'<div class="kpi-flex-label">{escape(str(label))}</div>'
            f'<div class="kpi-flex-value">{escape(str(value))}</div>'
            "</div>"
        )
        for label, value in metrics
    )
    st.markdown(
        f'<div class="{grid_class}">{cards_html}</div>',
        unsafe_allow_html=True,
    )


def render_labeled_bar_chart(
    records: list[dict[str, object]],
    category_field: str,
    value_field: str,
    category_title: str,
    value_title: str,
    height: int = 320,
) -> None:
    if not records:
        st.info("No chart data available yet.")
        return

    chart_df = pd.DataFrame(records)
    chart = (
        alt.Chart(chart_df)
        .mark_bar(cornerRadius=8, color="#c9181e", size=28)
        .encode(
            x=alt.X(
                f"{value_field}:Q",
                title=value_title,
                axis=alt.Axis(labelColor="#212121", titleColor="#212121", gridColor="#ececf3", tickColor="#d8dae2"),
            ),
            y=alt.Y(
                f"{category_field}:N",
                title=category_title,
                sort="-x",
                axis=alt.Axis(labelColor="#212121", titleColor="#212121", labelLimit=220),
            ),
            tooltip=list(chart_df.columns),
        )
        .properties(height=height, padding={"left": 8, "right": 20, "top": 8, "bottom": 8})
        .configure(background="#ffffff")
        .configure_view(strokeOpacity=0)
        .configure_axis(domainColor="#d9dbe3")
    )
    st.altair_chart(chart, use_container_width=True)


def render_admin_log(rows: list[sqlite3.Row]) -> None:
    if not rows:
        st.info("No transactions yet.")
        return

    table_rows = []
    for row in rows:
        table_rows.append(
            {
                "Time": fmt_dt(row["timestamp"]),
                "User": row["name"],
                "Card ID": row["card_id"],
                "Action": action_label(row["type"]),
                "Location": row["location"] or "-",
                "Amount": fmt_money(row["amount"]),
                "Balance After": fmt_balance(row["balance_after"]),
            }
        )

    st.dataframe(table_rows, use_container_width=True, hide_index=True)


def admin_action_form(users: list[sqlite3.Row]) -> None:
    user_options = {
        f"{row['name']} | {row['card_id']} | {fmt_balance(row['balance'])}": row["id"]
        for row in users
    }
    selected_label = st.selectbox("Select user", list(user_options.keys()), key="admin_selected_user")
    selected_user_id = user_options[selected_label]
    st.session_state["admin_selected_user_id"] = selected_user_id
    selected_user = next(row for row in users if row["id"] == selected_user_id)

    st.caption(
        f"Campus ID: {selected_user['campus_id']} | "
        f"Phone: {selected_user['phone']} | "
        f"Role: {selected_user['role'].title()}"
    )

    action = st.selectbox("Action", ["Entry", "Exit", "Payment", "Top-up"], key="admin_action")
    if action in {"Entry", "Exit"}:
        location = st.selectbox("Gate", GATE_LOCATIONS, key="admin_gate")
    else:
        location_options = PAYMENT_LOCATIONS if action == "Payment" else ["Admin Counter", "Finance Office"]
        location = st.selectbox("Location", location_options, key="admin_location")

    amount = None
    if action in {"Payment", "Top-up"}:
        amount = st.number_input(
            "Amount (RM)",
            min_value=1.0 if action == "Payment" else float(MIN_TOP_UP),
            max_value=float(MAX_WALLET_BALANCE),
            value=3.0 if action == "Payment" else 25.0,
            step=1.0,
            key="admin_amount",
        )

    if st.button("Process NFC Tap", key="process_nfc_tap", use_container_width=True):
        if action == "Entry":
            ok, message = parking_entry(selected_user_id, location)
        elif action == "Exit":
            ok, message = parking_exit(selected_user_id, location)
        elif action == "Payment":
            ok, message = make_payment(selected_user_id, float(amount), location)
        else:
            ok, message = top_up_wallet(selected_user_id, float(amount), location, "ADMIN_TOP_UP")

        push_flash("success" if ok else "error", message)
        st.rerun()


def render_admin_portal() -> None:
    users = list_users()
    audit = audit_summary()
    gate_activity = gate_activity_snapshot()
    merchant_usage = merchant_usage_snapshot()
    alerts = suspicious_access_alerts()
    failed_taps = failed_tap_history()
    selected_user_id = st.session_state.get("admin_selected_user_id")

    busiest_gate = "-"
    total_gate_taps = 0
    if gate_activity:
        busiest = max(gate_activity, key=lambda row: row["entries"] + row["exits"])
        busiest_gate = busiest["gate"]
        total_gate_taps = sum(row["entries"] + row["exits"] for row in gate_activity)

    total_wallet_transactions = sum(row["transactions"] for row in merchant_usage)
    top_merchant = merchant_usage[0]["merchant"] if merchant_usage else "-"
    total_wallet_spend = sum(row["total_spend"] for row in merchant_usage)

    st.markdown(
        f"""
        <div class="admin-kpis">
            <div class="kpi-card">
                <div class="kpi-label">Seeded users</div>
                <div class="kpi-value">{user_count()}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Open parking sessions</div>
                <div class="kpi-value">{open_parking_count()}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Wallet total</div>
                <div class="kpi-value">{fmt_balance(wallet_total())}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Busiest gate</div>
                <div class="kpi-value">{busiest_gate}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([0.95, 1.45])
    with left:
        st.markdown('<div class="portal-section-title">Tap Simulator</div>', unsafe_allow_html=True)
        admin_action_form(users)

        st.write("")
        st.markdown('<div class="portal-section-title">Access Monitoring</div>', unsafe_allow_html=True)
        alert_cols = st.columns(2)
        with alert_cols[0]:
            st.markdown('<div class="field-title">Access Alerts</div>', unsafe_allow_html=True)
            render_alert_list(alerts)
        with alert_cols[1]:
            st.markdown('<div class="field-title">Failed Tap History</div>', unsafe_allow_html=True)
            render_failed_tap_table(failed_taps)

        st.write("")
        render_chart_kpis(
            [
                ("Free same-gate exits", str(audit["free_same_gate"])),
                ("Cross-gate quick exits", str(audit["cross_gate_quick"])),
                ("Low-balance accounts", str(audit["low_balance"])),
            ]
        )

    with right:
        tabs = st.tabs(
            [
                "Live Log",
                "Demo Accounts",
                "Gate Throughput",
                "Wallet Adoption",
                "Unified Credential",
                "Visitor / LPR",
            ]
        )

        with tabs[0]:
            st.markdown('<div class="portal-section-title">Live Transaction Log</div>', unsafe_allow_html=True)
            render_admin_log(all_transactions())

        with tabs[1]:
            render_demo_accounts_panel()

        with tabs[2]:
            st.markdown('<div class="portal-section-title">Gate Throughput</div>', unsafe_allow_html=True)
            render_chart_kpis(
                [
                    ("Total gate taps", str(total_gate_taps)),
                    ("Busiest gate", busiest_gate),
                    ("Open sessions", str(open_parking_count())),
                ]
            )
            st.dataframe(gate_activity, use_container_width=True, hide_index=True)
            render_labeled_bar_chart(
                [{"Gate": row["gate"], "Total Taps": row["entries"] + row["exits"]} for row in gate_activity],
                category_field="Gate",
                value_field="Total Taps",
                category_title="Gate",
                value_title="Total taps",
            )

        with tabs[3]:
            st.markdown('<div class="portal-section-title">Wallet Adoption</div>', unsafe_allow_html=True)
            render_chart_kpis(
                [
                    ("Wallet transactions", str(total_wallet_transactions)),
                    ("Top merchant", top_merchant),
                    ("Total spend", fmt_balance(total_wallet_spend)),
                ]
            )
            st.dataframe(
                [
                    {
                        "Merchant": row["merchant"],
                        "Transactions": row["transactions"],
                        "Total Spend": fmt_balance(row["total_spend"]),
                    }
                    for row in merchant_usage
                ],
                use_container_width=True,
                hide_index=True,
            )
            render_labeled_bar_chart(
                [{"Merchant": row["merchant"], "Transactions": row["transactions"]} for row in merchant_usage],
                category_field="Merchant",
                value_field="Transactions",
                category_title="Merchant",
                value_title="Transactions",
            )

        with tabs[4]:
            st.markdown('<div class="portal-section-title">Unified Credential</div>', unsafe_allow_html=True)
            credential_options = {
                f"{row['name']} | {row['role'].title()} | {row['card_id']}": row["id"]
                for row in users
            }
            default_index = 0
            if selected_user_id and selected_user_id in credential_options.values():
                default_index = list(credential_options.values()).index(selected_user_id)
            chosen_label = st.selectbox(
                "Select user",
                list(credential_options.keys()),
                index=default_index,
                key="unified_user_selector",
            )
            render_unified_profile(credential_options[chosen_label])

        with tabs[5]:
            render_visitor_lane_panel()


def render_header() -> None:
    st.title(APP_TITLE)


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### Portal")
        portal = st.radio(
            "View",
            ["User Portal", "Admin Portal"],
            index=0 if st.session_state.portal == "User Portal" else 1,
        )
        st.session_state.portal = portal

        if st.session_state.get("user_id"):
            st.markdown("---")
            if st.button("Log Out User Session", key="sidebar_logout", use_container_width=True):
                st.session_state.user_id = None
                st.session_state.user_view = "Dashboard"
                push_flash("info", "You have been logged out.")
                st.rerun()


def main() -> None:
    inject_styles()
    init_state()
    init_db()
    render_sidebar()
    render_header()
    show_flash_messages()

    if st.session_state.portal == "User Portal":
        render_user_portal()
    else:
        render_admin_portal()


if __name__ == "__main__":
    main()
