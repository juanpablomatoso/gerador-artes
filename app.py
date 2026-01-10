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
    .tag-urgente { background-color: #dc3545; color: white; }
    .tag-normal { background-color: #e9ecef; color: #495057; }
    .tag-programar { background-color: #ffc107; color: #000; }
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
    "User-Agent": os.getenv(
        "DT_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
}

REQUEST_TIMEOUT = int(os.getenv("DT_REQUEST_TIMEOUT", "12"))

# ============================================================
# 4) SEGURANÇA: SENHAS (SEM HARDCODE)
# ============================================================

def make_password_hash(password: str, iterations: int = 200_000) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
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
        test = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
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

    juan_hash = auth.get("juan") or os.getenv("DT_AUTH_JUAN", "").strip()
    brayan_hash = auth.get("brayan") or os.getenv("DT_AUTH_BRAYAN", "").strip()

    return {"juan": juan_hash, "brayan": brayan_hash}

AUTH_HASHES = load_auth_hashes()
AUTH_CONFIG_OK = bool(AUTH_HASHES.get("juan")) and bool(AUTH_HASHES.get("brayan"))

# ============================================================
# 5) BANCO DE DADOS (ROBUSTO)
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

    # NOVA AGENDA EDITORIAL (PROFISSIONAL)
    c.execute("""
    CREATE TABLE IF NOT EXISTS agenda (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        descricao TEXT,
        data_ref TEXT,
        status TEXT DEFAULT 'Pendente',
        criado_em TEXT
    )
    """)

    # TABELA DE PAUTAS (MANTIDA)
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS pautas_trabalho
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            link_ref TEXT,
            status TEXT,
            data_envio TEXT,
            prioridade TEXT,
            observacao TEXT
        )
        """
    )

    conn.commit()
    conn.close()

init_db()

# ============================================================
# 6) HTTP HELPERS (COM TIMEOUT + TRATAMENTO)
# ============================================================
@st.cache_resource(show_spinner=False)
def get_requests_session(headers: dict):
    s = requests.Session()
    s.headers.update(headers)
    return s

SESSION = get_requests_session(HEADERS)

def safe_get_text(url: str) -> str:
    try:
        r = SESSION.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        if not r.encoding:
            r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except requests.exceptions.Timeout:
        raise RuntimeError("Tempo limite excedido ao acessar a página.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Falha HTTP ao acessar a página: {e}")

def safe_get_bytes(url: str) -> bytes:
    try:
        r = SESSION.get(url, timeout=REQUEST_TIMEOUT, stream=True, allow_redirects=True)
        r.raise_for_status()
        return r.content
    except requests.exceptions.Timeout:
        raise RuntimeError("Tempo limite excedido ao baixar a imagem.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Falha HTTP ao baixar a imagem: {e}")

# ============================================================
# 7) SCRAPING + ARTE (ROBUSTO)
# ============================================================
def extrair_titulo(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        t = h1.get_text(" ", strip=True)
        if t:
            return t
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    return "Sem título"

def normalizar_url(base: str, candidate: str) -> str:
    if not candidate:
        return ""
    return urljoin(base, candidate)

def encontrar_primeira_imagem_util(base_url: str, soup: BeautifulSoup) -> str:
    candidatos = []
    corpo = soup.find(class_="post-body") or soup.find("article") or soup

    for img in corpo.find_all("img"):
        src = (img.get("src") or "").strip()
        data_src = (img.get("data-src") or "").strip()
        data_lazy = (img.get("data-lazy-src") or "").strip()
        pick = src or data_src or data_lazy
        if not pick:
            continue

        full = normalizar_url(base_url, pick)
        low = full.lower()

        if "logo" in low or "icon" in low or "sprite" in low:
            continue

        if not re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", low):
            candidatos.append(full)
            continue

        return full

    return candidatos[0] if candidatos else ""

def garantir_fonte():
    if not os.path.exists(CAMINHO_FONTE):
        raise FileNotFoundError(
            f"Fonte não encontrada: {CAMINHO_FONTE}. "
            f"Ajuste DT_FONTE_PATH ou coloque o arquivo no mesmo diretório."
        )

def aplicar_template_se_existir(base_img: Image.Image, template_path: str, size: tuple):
    if os.path.exists(template_path):
        tmp = Image.open(template_path).convert("RGBA").resize(size)
        base_img.alpha_composite(tmp)

def processar_artes_integrado(url: str, tipo_solicitado: str) -> Image.Image:
    garantir_fonte()

    html = safe_get_text(url)
    soup = BeautifulSoup(html, "html.parser")

    titulo = extrair_titulo(soup)
    img_url = encontrar_primeira_imagem_util(url, soup)

    if not img_url:
        raise ValueError("Não foi encontrada uma imagem válida na matéria (ou só há logos/ícones).")

    img_original = Image.open(io.BytesIO(safe_get_bytes(img_url))).convert("RGBA")
    larg_o, alt_o = img_original.size
    if alt_o == 0:
        raise ValueError("Imagem inválida (altura zero).")

    prop_o = larg_o / alt_o

    if tipo_solicitado == "FEED":
        TAMANHO_FEED = 1000

        if prop_o > 1.0:
            n_alt = TAMANHO_FEED
            n_larg = int(n_alt * prop_o)
            img_redim = img_original.resize((n_larg, n_alt), Image.LANCZOS)
            margem = (n_larg - TAMANHO_FEED) // 2
            fundo = img_redim.crop((margem, 0, margem + TAMANHO_FEED, TAMANHO_FEED))
        else:
            n_larg = TAMANHO_FEED
            n_alt = int(n_larg / prop_o)
            img_redim = img_original.resize((n_larg, n_alt), Image.LANCZOS)
            margem = (n_alt - TAMANHO_FEED) // 2
            fundo = img_redim.crop((0, margem, TAMANHO_FEED, margem + TAMANHO_FEED))

        fundo = fundo.convert("RGBA")
        aplicar_template_se_existir(fundo, TEMPLATE_FEED, (TAMANHO_FEED, TAMANHO_FEED))

        draw = ImageDraw.Draw(fundo)

        tam = 85
        while tam > 20:
            fonte = ImageFont.truetype(CAMINHO_FONTE, tam)
            try:
                limite = int(662 / (fonte.getlength("W") * 0.55))
            except Exception:
                limite = 26

            linhas = textwrap.wrap(titulo, width=max(10, limite))
            alt_bloco = (len(linhas) * tam) + ((len(linhas) - 1) * 4)
            if alt_bloco <= 165 and len(linhas) <= 3:
                break
            tam -= 1

        y = 811 - (alt_bloco // 2)
        for lin in linhas:
            bbox = draw.textbbox((0, 0), lin, font=fonte)
            larg_l = bbox[2] - bbox[0]
            draw.text((488 - (larg_l // 2), y), lin, fill="black", font=fonte)
            y += tam + 4

        return fundo.convert("RGB")

    # STORY
    LARG_STORY, ALT_STORY = 940, 541
    ratio_a = LARG_STORY / ALT_STORY

    if prop_o > ratio_a:
        ns_alt = ALT_STORY
        ns_larg = int(ns_alt * prop_o)
    else:
        ns_larg = LARG_STORY
        ns_alt = int(ns_larg / prop_o)

    img_redim = img_original.resize((ns_larg, ns_alt), Image.LANCZOS)

    l_cut = (ns_larg - LARG_STORY) / 2
    t_cut = (ns_alt - ALT_STORY) / 2

    img_final = img_redim.crop((l_cut, t_cut, l_cut + LARG_STORY, t_cut + ALT_STORY))
    storie_canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 255))
    storie_canvas.paste(img_final, (69, 504))

    aplicar_template_se_existir(storie_canvas, TEMPLATE_STORIE, (1080, 1920))

    draw_s = ImageDraw.Draw(storie_canvas)

    tam_s = 60
    while tam_s > 20:
        fonte_s = ImageFont.truetype(CAMINHO_FONTE, tam_s)
        try:
            limite_s = int(912 / (fonte_s.getlength("W") * 0.55))
        except Exception:
            limite_s = 34

        linhas_s = textwrap.wrap(titulo, width=max(10, limite_s))
        alt_bloco_s = (len(linhas_s) * tam_s) + (len(linhas_s) * 10)
        if alt_bloco_s <= 300 and len(linhas_s) <= 4:
            break
        tam_s -= 2

    y_s = 1079
    for lin in linhas_s:
        draw_s.text((69, y_s), lin, fill="white", font=fonte_s)
        y_s += tam_s + 12

    return storie_canvas.convert("RGB")

# ============================================================
# 8) BUSCAR ÚLTIMAS (COM CACHE + URL ABSOLUTA)
# ============================================================
@st.cache_data(ttl=120)
def buscar_ultimas():
    try:
        base = "https://www.destaquetoledo.com.br/"
        html = safe_get_text(base)
        soup = BeautifulSoup(html, "html.parser")

        news = []
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if ".html" in href and "/20" in href:
                t = a.get_text(strip=True)
                if t and len(t) > 25:
                    news.append({"t": t, "u": urljoin(base, href)})

        seen = set()
        out = []
        for item in news:
            if item["u"] in seen:
                continue
            seen.add(item["u"])
            out.append(item)

        return out[:12]
    except Exception:
        return []

# ============================================================
# 9) LOGIN (VERSÃO OTIMIZADA E MODERNA)
# ============================================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    # Centralização da logo e título com estilo aprimorado
    st.markdown(
        """
        <div style="text-align: center; padding: 20px;">
            <h1 style="color: #004a99; margin-bottom: 0; font-family: sans-serif;">DESTAQUE TOLEDO</h1>
            <p style="color: #666; font-size: 1.1rem;">Painel de Controle Administrativo</p>
        </div>
        """, 
        unsafe_allow_html=True
    )

    _, col2, _ = st.columns([1, 1.2, 1])
    
    with col2:
        # Usando container com borda para dar aspecto de "card" de login
        with st.container(border=True):
            st.markdown("<h3 style='text-align: center; margin-top: 0;'>Acesso Restrito</h3>", unsafe_allow_html=True)
            
            if not AUTH_CONFIG_OK:
                st.error(
                    "⚠️ **Configuração Faltando**\n\n"
                    "As chaves de autenticação não foram detectadas.\n"
                    "Certifique-se de configurar os secrets no Streamlit Cloud."
                )
                st.stop()

            u = st.text_input("👤 Usuário", placeholder="Digite seu usuário").lower().strip()
            s = st.text_input("🔑 Senha", type="password", placeholder="Digite sua senha")
            
            # Recurso visual de "Mantenha-me conectado"
            manter_conectado = st.checkbox("Manter-se conectado", value=True)
            
            st.write("") # Espaçador
            
            if st.button("ENTRAR NO SISTEMA", use_container_width=True, type="primary"):
                if u in ("juan", "brayan") and verify_password(s, AUTH_HASHES.get(u, "")):
                    st.session_state.autenticado = True
                    st.session_state.perfil = u
                    st.session_state.manter_sessao = manter_conectado
                    st.toast(f"Bem-vindo, {u.capitalize()}!", icon="✅")
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos.")

        # Links auxiliares abaixo do card
        st.markdown(
            """
            <div style="text-align: center; margin-top: 20px;">
                <a href="https://www.destaquetoledo.com.br" target="_blank" style="text-decoration: none; color: #007bff; font-size: 0.85rem;">🌐 Acessar Site Público</a>
                <br><br>
                <small style="color: #999;">Suporte técnico: <a href="mailto:admin@destaquetoledo.com.br" style="color: #999;">Contato</a></small>
            </div>
            """, 
            unsafe_allow_html=True
        )

else:
    # ============================================================
    # 10) INTERFACE INTERNA
    # ============================================================
    st.markdown('<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1></div>', unsafe_allow_html=True)

    if st.session_state.perfil == "juan":
        st.markdown('<div class="boas-vindas">Bem-vindo, Juan!</div>', unsafe_allow_html=True)
        tab1, tab2, tab3 = st.tabs(["🎨 GERADOR DE ARTES", "📝 FILA DO BRAYAN", "📅 AGENDA"])

        # ---------------- TAB 1 ----------------
        with tab1:
            st.markdown(
                '<p class="descricao-aba">Aqui você gera automaticamente os posts para Instagram.</p>',
                unsafe_allow_html=True,
            )
            c1, col_preview = st.columns([1, 2])

            with c1:
                st.subheader("📰 Notícias Recentes")
                ultimas = buscar_ultimas()
                for i, item in enumerate(ultimas):
                    if st.button(item["t"], key=f"btn_{i}", use_container_width=True):
                        st.session_state.url_atual = item["u"]

            with col_preview:
                url_f = st.text_input("Link da Matéria:", value=st.session_state.get("url_atual", ""))
                if url_f:
                    if st.button("🖼️ GERAR FEED"):
                        st.image(processar_artes_integrado(url_f, "FEED"))

        # ---------------- TAB 2 ----------------
        with tab2:
            st.markdown(
                '<p class="descricao-aba">Envie as matérias que o Brayan deve postar.</p>',
                unsafe_allow_html=True,
            )

        # ---------------- TAB 3 (AGENDA) ----------------
        with tab3:
            st.markdown(
                '<p class="descricao-aba">Agenda editorial do portal: lembretes, pautas e tarefas do dia.</p>',
                unsafe_allow_html=True,
            )

    else:
        # ============================================================
        # PAINEL BRAYAN
        # ============================================================
        st.markdown('<div class="boas-vindas">Olá, Brayan! Bom trabalho.</div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="descricao-aba">Confira abaixo as matérias enviadas pelo Juan.</p>',
            unsafe_allow_html=True,
        )

    # ============================================================
    # SIDEBAR (FORA DO IF/ELSE, MAS DENTRO DO AUTENTICADO)
    # ============================================================
    with st.sidebar:
        st.write(f"Logado como: **{st.session_state.perfil.upper()}**")
        if st.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state.autenticado = False
            st.rerun()
