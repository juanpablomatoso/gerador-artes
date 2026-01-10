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
import hashlib, hmac, binascii, re

# ============================================================
# CONFIGURAÇÃO
# ============================================================
st.set_page_config(page_title="Painel Destaque Toledo", layout="wide", page_icon="🎨")

DB_PATH = "agenda_destaque.db"
CAMINHO_FONTE = "Shoika Bold.ttf"
TEMPLATE_FEED = "template_feed.png"
TEMPLATE_STORIE = "template_storie.png"
HEADERS = {"User-Agent": "Mozilla/5.0"}
REQUEST_TIMEOUT = 12

# ============================================================
# SEGURANÇA
# ============================================================
def make_password_hash(password: str, iterations: int = 200_000) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        _, it, salt, h = stored.split("$")
        test = hashlib.pbkdf2_hmac("sha256", password.encode(), binascii.unhexlify(salt), int(it))
        return hmac.compare_digest(test, binascii.unhexlify(h))
    except:
        return False

AUTH = st.secrets.get("AUTH", {})

# ============================================================
# BANCO DE DADOS
# ============================================================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

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
    # 🔹 LOG DE AÇÕES (NOVO)
    c.execute("""
    CREATE TABLE IF NOT EXISTS log_acoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        acao TEXT,
        pauta_id INTEGER,
        data_hora TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# 🔹 FUNÇÃO DE LOG (NOVO)
def registrar_log(usuario, acao, pauta_id=None):
    conn = get_conn()
    c = conn.cursor()
    data = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S")
    c.execute(
        "INSERT INTO log_acoes (usuario, acao, pauta_id, data_hora) VALUES (?,?,?,?)",
        (usuario, acao, pauta_id, data)
    )
    conn.commit()
    conn.close()

# ============================================================
# SCRAPING / ARTES (SEM ALTERAÇÕES)
# ============================================================
def processar_artes_integrado(url, tipo):
    html = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT).text
    soup = BeautifulSoup(html, "html.parser")
    titulo = soup.find("h1").get_text(strip=True)
    img_url = next(img["src"] for img in soup.find_all("img") if "logo" not in img["src"].lower())
    img = Image.open(io.BytesIO(requests.get(img_url, timeout=REQUEST_TIMEOUT).content)).convert("RGBA")

    if tipo == "FEED":
        img = img.resize((1000, 1000))
        return img.convert("RGB")

    canvas = Image.new("RGB", (1080, 1920), "black")
    canvas.paste(img.resize((940, 541)), (70, 500))
    return canvas

# 🔹 CACHE DE IMAGENS (NOVO)
@st.cache_data(ttl=3600)
def gerar_arte_cacheada(url, tipo):
    return processar_artes_integrado(url, tipo)

# ============================================================
# LOGIN
# ============================================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    with st.form("login"):
        u = st.text_input("Usuário").lower()
        s = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if u in AUTH and verify_password(s, AUTH[u]):
                st.session_state.autenticado = True
                st.session_state.perfil = u
                st.rerun()
            else:
                st.error("Acesso negado")

# ============================================================
# PAINEL INTERNO
# ============================================================
else:
    st.title("Painel Destaque Toledo")

    if st.session_state.perfil == "juan":
        tab1, tab2, tab3, tab4 = st.tabs([
            "🎨 Gerador",
            "📝 Fila Brayan",
            "📅 Agenda",
            "🔐 Segurança"
        ])

        with tab1:
            url = st.text_input("Link da matéria")
            if st.button("Gerar FEED"):
                img = gerar_arte_cacheada(url, "FEED")
                st.image(img)
            if st.button("Gerar STORY"):
                img = gerar_arte_cacheada(url, "STORY")
                st.image(img)

        with tab2:
            with st.form("envio"):
                t = st.text_input("Título")
                l = st.text_input("Link")
                p = st.selectbox("Prioridade", ["Normal", "Programar", "URGENTE"])
                if st.form_submit_button("Enviar"):
                    conn = get_conn()
                    c = conn.cursor()
                    hora = (datetime.utcnow() - timedelta(hours=3)).strftime("%H:%M")
                    c.execute(
                        "INSERT INTO pautas_trabalho (titulo, link_ref, status, data_envio, prioridade) VALUES (?,?,?,?,?)",
                        (t, l, "Pendente", hora, p)
                    )
                    conn.commit()
                    conn.close()
                    registrar_log("juan", "Enviou pauta")
                    st.success("Enviado")

        # 🔹 TELA DE TROCA DE SENHA (NOVA)
        with tab4:
            st.subheader("Trocar senha")
            alvo = st.selectbox("Usuário", ["juan", "brayan"])
            s1 = st.text_input("Nova senha", type="password")
            s2 = st.text_input("Confirmar", type="password")
            if st.button("Atualizar senha"):
                if s1 != s2 or not s1:
                    st.error("Senhas não conferem")
                else:
                    st.secrets["AUTH"][alvo] = make_password_hash(s1)
                    registrar_log("juan", f"Trocou senha de {alvo}")
                    st.success("Senha atualizada. Reinicie o app.")

    else:
        st.subheader("Fila do Juan")
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT id, titulo FROM pautas_trabalho WHERE status='Pendente'")
        for pid, tit in c.fetchall():
            st.write(tit)
            if st.button("Marcar como postado", key=pid):
                c.execute("UPDATE pautas_trabalho SET status='Concluído' WHERE id=?", (pid,))
                conn.commit()
                registrar_log("brayan", "Marcou como postado", pid)
                st.rerun()
        conn.close()
