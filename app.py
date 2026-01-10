import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import urljoin
import hashlib
import hmac
import binascii
import re

# ============================================================
# 1) CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="Painel Destaque Toledo",
    layout="wide",
    page_icon="🎨"
)

# ============================================================
# 2) ESTILIZAÇÃO CSS PROFISSIONAL
# ============================================================
st.markdown("""
<style>
.stApp { background-color: #f8f9fa; }
.topo-titulo {
    text-align: center;
    padding: 30px;
    background: linear-gradient(90deg, #004a99 0%, #007bff 100%);
    color: white;
    border-radius: 15px;
    margin-bottom: 25px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.card-pauta {
    background-color: white;
    padding: 20px;
    border-radius: 12px;
    border-left: 6px solid #004a99;
    margin-bottom: 15px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.card-urgente { border-left: 6px solid #dc3545; background-color: #fff5f5; }
.card-programar { border-left: 6px solid #ffc107; background-color: #fffdf5; }
.tag-status {
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: bold;
    text-transform: uppercase;
}
.tag-urgente { background-color: #dc3545; color: white; }
.tag-normal { background-color: #e9ecef; color: #495057; }
.tag-programar { background-color: #ffc107; color: #000; }
.obs-box {
    background-color: #e7f1ff;
    padding: 12px;
    border-radius: 8px;
    border: 1px dashed #004a99;
    margin-top: 10px;
    margin-bottom: 15px;
    font-style: italic;
}
.boas-vindas {
    font-size: 1.5rem;
    font-weight: bold;
    color: #004a99;
    margin-bottom: 10px;
}
.descricao-aba {
    color: #666;
    font-size: 0.95rem;
    margin-bottom: 20px;
    line-height: 1.4;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# 3) CONFIG / CONSTANTES
# ============================================================
DB_PATH = os.getenv("DT_DB_PATH", "agenda_destaque.db")
CAMINHO_FONTE = os.getenv("DT_FONTE_PATH", "Shoika Bold.ttf")
TEMPLATE_FEED = os.getenv("DT_TEMPLATE_FEED", "template_feed.png")
TEMPLATE_STORIE = os.getenv("DT_TEMPLATE_STORIE", "template_storie.png")

HEADERS = {
    "User-Agent": os.getenv(
        "DT_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
}

REQUEST_TIMEOUT = int(os.getenv("DT_REQUEST_TIMEOUT", "12"))

# ============================================================
# 4) SEGURANÇA: SENHAS
# ============================================================
def make_password_hash(password: str, iterations: int = 200_000) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations
    )
    return "pbkdf2_sha256$%d$%s$%s" % (
        iterations,
        binascii.hexlify(salt).decode("ascii"),
        binascii.hexlify(dk).decode("ascii"),
    )

def verify_password(password: str, stored: str) -> bool:
    try:
        algo, it_str, salt_hex, hash_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(it_str)
        salt = binascii.unhexlify(salt_hex.encode("ascii"))
        expected = binascii.unhexlify(hash_hex.encode("ascii"))
        test = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations
        )
        return hmac.compare_digest(test, expected)
    except Exception:
        return False

def load_auth_hashes():
    auth = {}
    try:
        if "AUTH" in st.secrets:
            auth = dict(st.secrets["AUTH"])
    except Exception:
        auth = {}

    return {
        "juan": auth.get("juan") or os.getenv("DT_AUTH_JUAN", "").strip(),
        "brayan": auth.get("brayan") or os.getenv("DT_AUTH_BRAYAN", "").strip(),
    }

AUTH_HASHES = load_auth_hashes()
AUTH_CONFIG_OK = bool(AUTH_HASHES["juan"]) and bool(AUTH_HASHES["brayan"])

# ============================================================
# 5) BANCO DE DADOS
# ============================================================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS pautas_trabalho (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            link_ref TEXT,
            status TEXT,
            data_envio TEXT,
            prioridade TEXT,
            observacao TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS agenda_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_ref TEXT,
            titulo TEXT,
            descricao TEXT,
            status TEXT,
            criado_por TEXT,
            criado_em TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ============================================================
# 6) SESSÃO HTTP
# ============================================================
@st.cache_resource(show_spinner=False)
def get_requests_session(headers):
    s = requests.Session()
    s.headers.update(headers)
    return s

SESSION = get_requests_session(HEADERS)

# ============================================================
# 7) LOGIN
# ============================================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown("<h2 style='text-align:center'>DESTAQUE TOLEDO</h2>", unsafe_allow_html=True)

    if not AUTH_CONFIG_OK:
        st.error("Configuração de autenticação ausente.")
        st.stop()

    u = st.text_input("Usuário").lower().strip()
    s = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        if u in AUTH_HASHES and verify_password(s, AUTH_HASHES[u]):
            st.session_state.autenticado = True
            st.session_state.perfil = u
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")
    st.stop()

# ============================================================
# 8) INTERFACE PRINCIPAL
# ============================================================
st.markdown('<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1></div>', unsafe_allow_html=True)
st.success(f"Logado como: {st.session_state.perfil.upper()}")
