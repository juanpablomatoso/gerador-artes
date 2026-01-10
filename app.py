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

# =========================================================
# CONFIGURAÇÃO STREAMLIT
# =========================================================
st.set_page_config(page_title="Painel Destaque Toledo", layout="wide", page_icon="🎨")

# =========================================================
# CSS
# =========================================================
st.markdown("""
<style>
.stApp { background-color: #f8f9fa; }
.topo-titulo {
    text-align:center; padding:30px;
    background:linear-gradient(90deg,#004a99,#007bff);
    color:white; border-radius:15px; margin-bottom:25px;
}
.card-pauta {
    background:white; padding:20px; border-radius:12px;
    border-left:6px solid #004a99; margin-bottom:15px;
}
.card-urgente { border-left-color:#dc3545; background:#fff5f5; }
.card-programar { border-left-color:#ffc107; background:#fffdf5; }
.tag-status {
    padding:4px 12px; border-radius:20px;
    font-size:.75rem; font-weight:bold;
}
.tag-urgente { background:#dc3545; color:white; }
.tag-programar { background:#ffc107; color:black; }
.tag-normal { background:#e9ecef; color:#495057; }
.obs-box {
    background:#e7f1ff; padding:12px; border-radius:8px;
    border:1px dashed #004a99; margin-bottom:15px;
}
.boas-vindas { font-size:1.5rem; font-weight:bold; color:#004a99; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# CONSTANTES
# =========================================================
DB_PATH = "agenda_destaque.db"
CAMINHO_FONTE = "Shoika Bold.ttf"
TEMPLATE_FEED = "template_feed.png"
TEMPLATE_STORIE = "template_storie.png"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 12

# =========================================================
# SENHAS (HASH)
# =========================================================
def make_password_hash(password: str, iterations: int = 200_000) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        algo, it, salt, hashv = stored.split("$")
        test = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            binascii.unhexlify(salt),
            int(it)
        )
        return hmac.compare_digest(test, binascii.unhexlify(hashv))
    except:
        return False

AUTH = st.secrets.get("AUTH", {})
AUTH_OK = "juan" in AUTH and "brayan" in AUTH

# =========================================================
# BANCO
# =========================================================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    c = get_conn().cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS pautas_trabalho (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT, link_ref TEXT,
            status TEXT, data_envio TEXT,
            prioridade TEXT, observacao TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS log_acoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT, acao TEXT,
            pauta_id INTEGER, data_hora TEXT
        )
    """)
    c.connection.commit()

init_db()

def registrar_log(usuario, acao, pauta_id=None):
    data = (datetime.utcnow()-timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
    c = get_conn().cursor()
    c.execute("INSERT INTO log_acoes VALUES (NULL,?,?,?,?)",
              (usuario, acao, pauta_id, data))
    c.connection.commit()

# =========================================================
# CACHE REQUESTS
# =========================================================
@st.cache_resource
def session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s

# =========================================================
# ARTES
# =========================================================
def extrair_titulo(soup):
    return soup.find("h1").get_text(strip=True) if soup.find("h1") else "Sem título"

def encontrar_imagem(base, soup):
    for img in soup.find_all("img"):
        src = img.get("src","")
        if src and "logo" not in src.lower():
            return urljoin(base, src)
    return ""

@st.cache_data(ttl=3600)
def gerar_arte_cacheada(url, tipo):
    html = session().get(url, timeout=TIMEOUT).text
    soup = BeautifulSoup(html, "html.parser")
    titulo = extrair_titulo(soup)
    img_url = encontrar_imagem(url, soup)
    if not img_url:
        raise Exception("Matéria sem imagem válida")

    img = Image.open(io.BytesIO(session().get(img_url).content)).convert("RGBA")

    if tipo == "FEED":
        img = img.resize((1000,1000), Image.LANCZOS)
    else:
        canvas = Image.new("RGBA",(1080,1920),(0,0,0))
        img = img.resize((940,541), Image.LANCZOS)
        canvas.paste(img,(69,504))
        img = canvas

    draw = ImageDraw.Draw(img)
    fonte = ImageFont.truetype(CAMINHO_FONTE, 48)
    draw.text((40,40), titulo, fill="white", font=fonte)

    return img.convert("RGB")

# =========================================================
# LOGIN
# =========================================================
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.markdown("<div class='topo-titulo'><h1>DESTAQUE TOLEDO</h1></div>", unsafe_allow_html=True)

    if not AUTH_OK:
        st.error("Secrets de autenticação não configurados.")
        st.stop()

    u = st.text_input("Usuário").lower().strip()
    s = st.text_input("Senha", type="password")

    if st.button("ENTRAR"):
        if u in AUTH and verify_password(s, AUTH[u]):
            st.session_state.auth = True
            st.session_state.perfil = u
            st.rerun()
        else:
            st.error("Acesso negado.")

# =========================================================
# PAINEL
# =========================================================
else:
    st.markdown("<div class='topo-titulo'><h1>DESTAQUE TOLEDO</h1></div>", unsafe_allow_html=True)

    if st.session_state.perfil == "juan":
        tab1, tab2, tab3 = st.tabs(["🎨 ARTES", "📝 FILA", "🔐 SEGURANÇA"])

        # ARTES
        with tab1:
            url = st.text_input("URL da matéria")
            c1, c2 = st.columns(2)
            if c1.button("GERAR FEED"):
                img = gerar_arte_cacheada(url,"FEED")
                st.image(img)
            if c2.button("GERAR STORY"):
                img = gerar_arte_cacheada(url,"STORY")
                st.image(img)

        # FILA
        with tab2:
            with st.form("envio"):
                t = st.text_input("Título")
                l = st.text_input("Link")
                o = st.text_area("Obs")
                p = st.selectbox("Prioridade",["Normal","Programar","URGENTE"])
                if st.form_submit_button("ENVIAR"):
                    hora = (datetime.utcnow()-timedelta(hours=3)).strftime("%H:%M")
                    c = get_conn().cursor()
                    c.execute("INSERT INTO pautas_trabalho VALUES (NULL,?,?,?, ?,?,?)",
                              (t,l,"Pendente",hora,p,o))
                    c.connection.commit()
                    registrar_log("juan","Enviou pauta")
                    st.success("Enviado")

        # SEGURANÇA
        with tab3:
            alvo = st.selectbox("Usuário",["juan","brayan"])
            n1 = st.text_input("Nova senha", type="password")
            n2 = st.text_input("Confirmar senha", type="password")
            if st.button("ALTERAR SENHA"):
                if n1 and n1==n2:
                    st.secrets["AUTH"][alvo] = make_password_hash(n1)
                    registrar_log("juan",f"Alterou senha de {alvo}")
                    st.success("Senha alterada. Reinicie o app.")
                else:
                    st.error("Senhas não conferem")

    # BRAYAN
    else:
        st.markdown("<div class='boas-vindas'>Olá, Brayan</div>", unsafe_allow_html=True)
        c = get_conn().cursor()
        c.execute("SELECT * FROM pautas_trabalho WHERE status='Pendente'")
        for p in c.fetchall():
            st.markdown(f"<div class='card-pauta'><b>{p[1]}</b></div>", unsafe_allow_html=True)
            if st.button("MARCAR COMO POSTADO", key=p[0]):
                c.execute("UPDATE pautas_trabalho SET status='Concluído' WHERE id=?", (p[0],))
                c.connection.commit()
                registrar_log("brayan","Marcou como postado",p[0])
                st.rerun()

    if st.sidebar.button("SAIR"):
        st.session_state.auth = False
        st.rerun()
