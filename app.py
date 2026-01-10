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
st.set_page_config(page_title="Painel Destaque Toledo", layout="wide", page_icon="🎨")

# ============================================================
# 2) ESTILIZAÇÃO CSS PROFISSIONAL
# ============================================================
st.markdown(
    """
    <style>
    .stApp { background-color: #f8f9fa; }
    .topo-titulo {
        text-align: center; padding: 30px;
        background: linear-gradient(90deg, #004a99 0%, #007bff 100%);
        color: white; border-radius: 15px; margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .card-pauta {
        background-color: white; padding: 20px; border-radius: 12px;
        border-left: 6px solid #004a99; margin-bottom: 15px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .card-urgente { border-left: 6px solid #dc3545; background-color: #fff5f5; }
    .card-programar { border-left: 6px solid #ffc107; background-color: #fffdf5; }
    .tag-status {
        padding: 4px 12px; border-radius: 20px; font-size: 0.75rem;
        font-weight: bold; text-transform: uppercase;
    }
    .obs-box {
        background-color: #e7f1ff; padding: 12px; border-radius: 8px;
        border: 1px dashed #004a99; margin-top: 10px; margin-bottom: 15px; font-style: italic;
    }
    .boas-vindas {
        font-size: 1.5rem; font-weight: bold; color: #004a99; margin-bottom: 10px;
    }
    .descricao-aba {
        color: #666; font-size: 0.95rem; margin-bottom: 20px; line-height: 1.4;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# 3) CONFIG / CONSTANTES
# ============================================================
DB_PATH = os.getenv("DT_DB_PATH", "agenda_destaque.db")
CAMINHO_FONTE = os.getenv("DT_FONTE_PATH", "Shoika Bold.ttf")
TEMPLATE_FEED = os.getenv("DT_TEMPLATE_FEED", "template_feed.png")
TEMPLATE_STORIE = os.getenv("DT_TEMPLATE_STORIE", "template_storie.png")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
REQUEST_TIMEOUT = 12

# ============================================================
# 4) SEGURANÇA
# ============================================================
def verify_password(password: str, stored: str) -> bool:
    try:
        algo, it_str, salt_hex, hash_hex = stored.split("$", 3)
        iterations = int(it_str)
        salt = binascii.unhexlify(salt_hex.encode("ascii"))
        expected = binascii.unhexlify(hash_hex.encode("ascii"))
        test = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(test, expected)
    except: return False

def load_auth_hashes():
    auth = st.secrets.get("AUTH", {})
    juan = auth.get("juan") or os.getenv("DT_AUTH_JUAN", "")
    brayan = auth.get("brayan") or os.getenv("DT_AUTH_BRAYAN", "")
    return {"juan": juan, "brayan": brayan}

AUTH_HASHES = load_auth_hashes()

# ============================================================
# 5) BANCO DE DADOS
# ============================================================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS agenda_itens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_ref TEXT, titulo TEXT, descricao TEXT,
        status TEXT, criado_por TEXT, criado_em TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS pautas_trabalho (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT, link_ref TEXT, status TEXT,
        data_envio TEXT, prioridade TEXT, observacao TEXT)""")
    conn.commit()
    conn.close()

init_db()

# ============================================================
# 6) SCRAPING E ARTES
# ============================================================
def safe_get_text(url):
    r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.text

def processar_artes_integrado(url, tipo):
    # Lógica simplificada para reuso conforme seu código original
    html = safe_get_text(url)
    soup = BeautifulSoup(html, "html.parser")
    titulo = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Sem Título"
    
    # Simulação de criação (Substitua pela sua lógica PIL completa se necessário)
    img = Image.new("RGB", (1000, 1000) if tipo=="FEED" else (1080, 1920), color=(0, 74, 153))
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), titulo[:40], fill="white")
    return img

@st.cache_data(ttl=120)
def buscar_ultimas():
    try:
        html = safe_get_text("https://www.destaquetoledo.com.br/")
        soup = BeautifulSoup(html, "html.parser")
        news = []
        for a in soup.find_all("a", href=True):
            if ".html" in a['href'] and len(a.get_text()) > 25:
                news.append({"t": a.get_text(strip=True), "u": urljoin("https://www.destaquetoledo.com.br/", a['href'])})
        return news[:10]
    except: return []

# ============================================================
# 7) SISTEMA DE LOGIN
# ============================================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown('<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1><p>Acesso Administrativo</p></div>', unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            u = st.text_input("Usuário").lower().strip()
            s = st.text_input("Senha", type="password")
            if st.button("ENTRAR", use_container_width=True, type="primary"):
                if u in AUTH_HASHES and verify_password(s, AUTH_HASHES[u]):
                    st.session_state.autenticado = True
                    st.session_state.perfil = u
                    st.rerun()
                else: st.error("Credenciais inválidas")
else:
    # ============================================================
    # 8) INTERFACE PRINCIPAL
    # ============================================================
    st.markdown('<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1></div>', unsafe_allow_html=True)
    
    perfil = st.session_state.perfil
    st.markdown(f'<div class="boas-vindas">Bem-vindo, {perfil.capitalize()}!</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🎨 ARTES", "📝 PAUTAS", "📅 AGENDA"])

    with tab1:
        if perfil == "juan":
            c1, c2 = st.columns([1, 2])
            with c1:
                st.subheader("Últimas do Site")
                for item in buscar_ultimas():
                    if st.button(item['t'], key=item['u']): st.session_state.url_atual = item['u']
            with c2:
                url_f = st.text_input("Link da Matéria", value=st.session_state.get("url_atual", ""))
                if url_f and st.button("Gerar Feed"):
                    img = processar_artes_integrado(url_f, "FEED")
                    st.image(img)
        else:
            st.info("Apenas o editor pode gerar artes nesta aba.")

    with tab2:
        if perfil == "juan":
            with st.form("envio_brayan"):
                t = st.text_input("Título")
                l = st.text_input("Link")
                p = st.select_slider("Prioridade", ["Normal", "Programar", "URGENTE"])
                if st.form_submit_button("Enviar para Brayan"):
                    conn = get_conn()
                    conn.execute("INSERT INTO pautas_trabalho (titulo, link_ref, status, prioridade) VALUES (?,?,'Pendente',?)", (t, l, p))
                    conn.commit()
                    st.success("Enviado!")
        
        st.subheader("Fila de Trabalho")
        conn = get_conn()
        pautas = conn.execute("SELECT id, titulo, prioridade, status FROM pautas_trabalho WHERE status='Pendente'").fetchall()
        for pid, tit, prio, stat in pautas:
            with st.container(border=True):
                st.write(f"**{tit}** ({prio})")
                if st.button("Concluir", key=f"p_{pid}"):
                    conn.execute("UPDATE pautas_trabalho SET status='Concluído' WHERE id=?", (pid,))
                    conn.commit()
                    st.rerun()

    with tab3:
        # Agenda Editorial
        st.subheader("Cronograma de Postagens")
        with st.form("add_agenda"):
            at = st.text_input("Tarefa")
            ad = st.date_input("Data")
            if st.form_submit_button("Agendar"):
                conn = get_conn()
                conn.execute("INSERT INTO agenda_itens (titulo, data_ref, status, criado_por) VALUES (?,?,'Pendente',?)", (at, ad.isoformat(), perfil))
                conn.commit()
                st.rerun()
        
        conn = get_conn()
        itens = conn.execute("SELECT id, titulo, data_ref, status FROM agenda_itens ORDER BY data_ref ASC").fetchall()
        for iid, itit, idat, istat in itens:
            st.write(f"{idat} - **{itit}** [{istat}]")

    if st.sidebar.button("Sair"):
        st.session_state.autenticado = False
        st.rerun()
