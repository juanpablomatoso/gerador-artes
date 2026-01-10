import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image
import io
import os
import sqlite3
from datetime import datetime, timedelta
import hashlib

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="Painel Destaque Toledo",
    layout="wide",
    page_icon="🎨"
)

HEADERS = {"User-Agent": "Mozilla/5.0"}

# =========================
# CSS
# =========================
st.markdown("""
<style>
.stApp { background-color: #f8f9fa; }
.topo-titulo {
    text-align: center; padding: 30px;
    background: linear-gradient(90deg, #004a99, #007bff);
    color: white; border-radius: 15px; margin-bottom: 25px;
}
.card-pauta {
    background: white; padding: 20px; border-radius: 12px;
    border-left: 6px solid #004a99; margin-bottom: 15px;
}
.card-urgente { border-left-color: #dc3545; background: #fff5f5; }
.card-programar { border-left-color: #ffc107; background: #fffdf5; }
.tag-status {
    padding: 4px 12px; border-radius: 20px;
    font-size: .75rem; font-weight: bold;
}
.tag-urgente { background: #dc3545; color: white; }
.tag-programar { background: #ffc107; color: black; }
.tag-normal { background: #e9ecef; color: #495057; }
.obs-box {
    background: #e7f1ff; padding: 12px;
    border-radius: 8px; border: 1px dashed #004a99;
}
</style>
""", unsafe_allow_html=True)

# =========================
# BANCO DE DADOS
# =========================
def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def init_db():
    conn = sqlite3.connect("agenda_destaque.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            usuario TEXT PRIMARY KEY,
            senha_hash TEXT
        )
    """)

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

    conn.commit()
    conn.close()

def criar_usuarios_padrao():
    conn = sqlite3.connect("agenda_destaque.db")
    c = conn.cursor()

    usuarios = {
        "juan": "juan123",
        "brayan": "brayan123"
    }

    for u, s in usuarios.items():
        c.execute(
            "INSERT OR IGNORE INTO usuarios VALUES (?,?)",
            (u, hash_senha(s))
        )

    conn.commit()
    conn.close()

init_db()
criar_usuarios_padrao()

# =========================
# LOGIN
# =========================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

def autenticar(usuario, senha):
    conn = sqlite3.connect("agenda_destaque.db")
    c = conn.cursor()
    c.execute("SELECT senha_hash FROM usuarios WHERE usuario=?", (usuario,))
    dado = c.fetchone()
    conn.close()

    if dado and dado[0] == hash_senha(senha):
        return True
    return False

if not st.session_state.autenticado:
    st.markdown('<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1><p>Painel Administrativo</p></div>', unsafe_allow_html=True)

    with st.form("login"):
        u = st.text_input("Usuário").lower().strip()
        s = st.text_input("Senha", type="password")
        if st.form_submit_button("ENTRAR"):
            if autenticar(u, s):
                st.session_state.autenticado = True
                st.session_state.perfil = u
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos")

    st.stop()

# =========================
# FUNÇÕES
# =========================
@st.cache_data(ttl=300)
def buscar_ultimas():
    try:
        res = requests.get("https://www.destaquetoledo.com.br/", headers=HEADERS, timeout=10).text
        soup = BeautifulSoup(res, "html.parser")
        links = set()
        noticias = []

        for a in soup.find_all("a", href=True):
            texto = a.get_text(strip=True)
            href = a["href"]
            if ".html" in href and len(texto) > 30:
                if not href.startswith("http"):
                    href = "https://www.destaquetoledo.com.br" + href
                if href not in links:
                    links.add(href)
                    noticias.append({"t": texto, "u": href})

        return noticias[:12]
    except:
        return []

# =========================
# INTERFACE
# =========================
st.markdown('<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1></div>', unsafe_allow_html=True)

# =========================
# PAINEL JUAN
# =========================
if st.session_state.perfil == "juan":
    tab1, tab2 = st.tabs(["🎨 Gerador", "📝 Fila do Brayan"])

    with tab1:
        st.subheader("Últimas Notícias")
        for n in buscar_ultimas():
            if st.button(n["t"], use_container_width=True):
                st.session_state.url_atual = n["u"]

        st.text_input("Link da matéria", st.session_state.get("url_atual", ""))

    with tab2:
        with st.form("envio"):
            t = st.text_input("Título")
            l = st.text_input("Link")
            o = st.text_area("Observações")
            p = st.selectbox("Prioridade", ["Normal", "Programar", "URGENTE"])
            if st.form_submit_button("Enviar"):
                hora = (datetime.utcnow() - timedelta(hours=3)).strftime("%H:%M")
                conn = sqlite3.connect("agenda_destaque.db")
                c = conn.cursor()
                c.execute("""
                    INSERT INTO pautas_trabalho
                    (titulo, link_ref, status, data_envio, prioridade, observacao)
                    VALUES (?, ?, 'Pendente', ?, ?, ?)
                """, (t, l, hora, p, o))
                conn.commit()
                conn.close()
                st.success("Pauta enviada")
                st.rerun()

# =========================
# PAINEL BRAYAN
# =========================
else:
    st.subheader("Pautas Pendentes")

    conn = sqlite3.connect("agenda_destaque.db")
    c = conn.cursor()
    c.execute("""
        SELECT id, titulo, link_ref, data_envio, prioridade, observacao
        FROM pautas_trabalho
        WHERE status='Pendente'
        ORDER BY id DESC
    """)
    pautas = c.fetchall()
    conn.close()

    if not pautas:
        st.success("Nenhuma pauta pendente")

    for p in pautas:
        pid, tit, link, hora, prio, obs = p

        st.markdown(f"""
        <div class="card-pauta">
            <span class="tag-status">{prio}</span> | 🕒 {hora}
            <h3>{tit}</h3>
        </div>
        """, unsafe_allow_html=True)

        if obs:
            st.markdown(f"<div class='obs-box'>{obs}</div>", unsafe_allow_html=True)

        if link:
            st.link_button("Abrir matéria", link)

        if st.button("Marcar como postado", key=f"ok{pid}"):
            conn = sqlite3.connect("agenda_destaque.db")
            c = conn.cursor()
            c.execute("UPDATE pautas_trabalho SET status='Concluído' WHERE id=?", (pid,))
            conn.commit()
            conn.close()
            st.rerun()

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.write(f"Logado como **{st.session_state.perfil.upper()}**")
    if st.button("Sair"):
        st.session_state.autenticado = False
        st.rerun()
