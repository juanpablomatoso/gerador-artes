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
    /* Estilos para a Agenda */
    .card-agenda {
        background-color: #ffffff; padding: 15px; border-radius: 10px;
        border-left: 5px solid #007bff; margin-bottom: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .data-agenda { color: #004a99; font-weight: bold; font-size: 1.1rem; display: block; margin-bottom: 5px; }
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
# 4) SEGURANÇA: SENHAS
# ============================================================
def verify_password(password: str, stored: str) -> bool:
    try:
        algo, it_str, salt_hex, hash_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256": return False
        iterations = int(it_str)
        salt = binascii.unhexlify(salt_hex.encode("ascii"))
        expected = binascii.unhexlify(hash_hex.encode("ascii"))
        test = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(test, expected)
    except Exception: return False

def load_auth_hashes():
    auth = dict(st.secrets["AUTH"]) if "AUTH" in st.secrets else {}
    juan_hash = auth.get("juan") or os.getenv("DT_AUTH_JUAN", "").strip()
    brayan_hash = auth.get("brayan") or os.getenv("DT_AUTH_BRAYAN", "").strip()
    return {"juan": juan_hash, "brayan": brayan_hash}

AUTH_HASHES = load_auth_hashes()
AUTH_CONFIG_OK = bool(AUTH_HASHES.get("juan"))

# ============================================================
# 5) BANCO DE DADOS
# ============================================================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    # Tabela Agenda (Atualizada com ID para exclusão)
    c.execute("CREATE TABLE IF NOT EXISTS agenda (id INTEGER PRIMARY KEY AUTOINCREMENT, dia TEXT, pauta TEXT)")
    # Tabela Pautas
    c.execute("""
        CREATE TABLE IF NOT EXISTS pautas_trabalho
        (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, link_ref TEXT, 
         status TEXT, data_envio TEXT, prioridade TEXT, observacao TEXT)
    """)
    conn.commit()
    conn.close()

init_db()

# ============================================================
# 6) HTTP HELPERS
# ============================================================
@st.cache_resource(show_spinner=False)
def get_requests_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s

SESSION = get_requests_session()

def safe_get_text(url: str) -> str:
    r = SESSION.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text

def safe_get_bytes(url: str) -> bytes:
    r = SESSION.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.content

# ============================================================
# 7) PROCESSAMENTO DE IMAGEM (CÓDIGO COMPLETO)
# ============================================================
def extrair_titulo(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1: return h1.get_text(" ", strip=True)
    return soup.title.get_text(strip=True) if soup.title else "Sem título"

def encontrar_primeira_imagem_util(base_url: str, soup: BeautifulSoup) -> str:
    candidatos = []
    corpo = soup.find(class_="post-body") or soup.find("article") or soup
    for img in corpo.find_all("img"):
        src = (img.get("src") or img.get("data-src") or "").strip()
        if not src: continue
        full = urljoin(base_url, src)
        low = full.lower()
        if any(x in low for x in ["logo", "icon", "sprite"]): continue
        if re.search(r"\.(jpg|jpeg|png|webp)", low): return full
        candidatos.append(full)
    return candidatos[0] if candidatos else ""

def aplicar_template(base_img, path, size):
    if os.path.exists(path):
        tmp = Image.open(path).convert("RGBA").resize(size)
        base_img.alpha_composite(tmp)

def processar_artes_integrado(url: str, tipo_solicitado: str) -> Image.Image:
    if not os.path.exists(CAMINHO_FONTE):
        raise FileNotFoundError("Fonte .ttf não encontrada no servidor.")

    html = safe_get_text(url)
    soup = BeautifulSoup(html, "html.parser")
    titulo = extrair_titulo(soup)
    img_url = encontrar_primeira_imagem_util(url, soup)

    if not img_url: raise ValueError("Nenhuma imagem encontrada na matéria.")

    img_original = Image.open(io.BytesIO(safe_get_bytes(img_url))).convert("RGBA")
    larg_o, alt_o = img_original.size
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
        aplicar_template(fundo, TEMPLATE_FEED, (1000, 1000))
        draw = ImageDraw.Draw(fundo)
        
        tam = 85
        while tam > 20:
            fonte = ImageFont.truetype(CAMINHO_FONTE, tam)
            linhas = textwrap.wrap(titulo, width=int(662 / (fonte.getlength("W") * 0.015))) # Ajuste fino
            alt_bloco = (len(linhas) * tam)
            if alt_bloco <= 165 and len(linhas) <= 3: break
            tam -= 1

        y = 811 - (alt_bloco // 2)
        for lin in linhas:
            bbox = draw.textbbox((0, 0), lin, font=fonte)
            draw.text((488 - ((bbox[2]-bbox[0]) // 2), y), lin, fill="black", font=fonte)
            y += tam + 4
        return fundo.convert("RGB")

    else: # STORY
        LARG_STORY, ALT_STORY = 940, 541
        ratio_a = LARG_STORY / ALT_STORY
        if prop_o > ratio_a:
            ns_alt = ALT_STORY
            ns_larg = int(ns_alt * prop_o)
        else:
            ns_larg = LARG_STORY
            ns_alt = int(ns_larg / prop_o)
        
        img_redim = img_original.resize((ns_larg, ns_alt), Image.LANCZOS)
        l_cut, t_cut = (ns_larg - LARG_STORY) / 2, (ns_alt - ALT_STORY) / 2
        img_final = img_redim.crop((l_cut, t_cut, l_cut + LARG_STORY, t_cut + ALT_STORY))
        
        storie_canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 255))
        storie_canvas.paste(img_final, (69, 504))
        aplicar_template(storie_canvas, TEMPLATE_STORIE, (1080, 1920))
        
        draw_s = ImageDraw.Draw(storie_canvas)
        tam_s = 60
        while tam_s > 20:
            fonte_s = ImageFont.truetype(CAMINHO_FONTE, tam_s)
            linhas_s = textwrap.wrap(titulo, width=34)
            if (len(linhas_s) * tam_s) <= 300: break
            tam_s -= 2

        y_s = 1079
        for lin in linhas_s:
            draw_s.text((69, y_s), lin, fill="white", font=fonte_s)
            y_s += tam_s + 12
        return storie_canvas.convert("RGB")

# ============================================================
# 8) BUSCAR ÚLTIMAS NOTÍCIAS
# ============================================================
@st.cache_data(ttl=120)
def buscar_ultimas():
    try:
        base = "https://www.destaquetoledo.com.br/"
        soup = BeautifulSoup(safe_get_text(base), "html.parser")
        news = []
        for a in soup.find_all("a", href=True):
            href = a['href']
            if ".html" in href and "/20" in href:
                t = a.get_text(strip=True)
                if t and len(t) > 25: news.append({"t": t, "u": urljoin(base, href)})
        
        out = []
        seen = set()
        for i in news:
            if i['u'] not in seen:
                out.append(i); seen.add(i['u'])
        return out[:12]
    except: return []

# ============================================================
# 9) INTERFACE DE LOGIN
# ============================================================
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown('<div style="text-align: center; padding: 20px;"><h1 style="color: #004a99;">DESTAQUE TOLEDO</h1><p>Painel Administrativo</p></div>', unsafe_allow_html=True)
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
                else: st.error("Acesso Negado")
else:
    # ============================================================
    # 10) INTERFACE INTERNA (JUAN / BRAYAN)
    # ============================================================
    st.markdown('<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1></div>', unsafe_allow_html=True)

    if st.session_state.perfil == "juan":
        st.markdown(f'<div class="boas-vindas">Bem-vindo, {st.session_state.perfil.capitalize()}!</div>', unsafe_allow_html=True)
        tab1, tab2, tab3 = st.tabs(["🎨 GERADOR DE ARTES", "📝 FILA DO BRAYAN", "📅 AGENDA"])

        with tab1:
            st.markdown('<p class="descricao-aba">Gere artes para o Instagram rapidamente.</p>', unsafe_allow_html=True)
            c1, col_preview = st.columns([1, 2])
            with c1:
                st.subheader("📰 Notícias Recentes")
                for item in buscar_ultimas():
                    if st.button(item["t"], key=item["u"], use_container_width=True):
                        st.session_state.url_atual = item["u"]
            with col_preview:
                url_f = st.text_input("Link da Matéria:", value=st.session_state.get("url_atual", ""))
                if url_f:
                    ca, cb = st.columns(2)
                    if ca.button("🖼️ GERAR FEED", use_container_width=True, type="primary"):
                        try:
                            img = processar_artes_integrado(url_f, "FEED")
                            st.image(img)
                            buf = io.BytesIO()
                            img.save(buf, "JPEG", quality=95)
                            st.download_button("📥 BAIXAR FEED", buf.getvalue(), "feed.jpg", use_container_width=True)
                        except Exception as e: st.error(f"Erro: {e}")
                    
                    if cb.button("📱 GERAR STORY", use_container_width=True):
                        try:
                            img = processar_artes_integrado(url_f, "STORY")
                            st.image(img, width=280)
                            buf = io.BytesIO()
                            img.save(buf, "JPEG", quality=95)
                            st.download_button("📥 BAIXAR STORY", buf.getvalue(), "story.jpg", use_container_width=True)
                        except Exception as e: st.error(f"Erro: {e}")

        with tab2:
            st.markdown('<p class="descricao-aba">Envie pautas diretamente para o painel do Brayan.</p>', unsafe_allow_html=True)
            with st.form("envio_brayan"):
                f_tit = st.text_input("Título da Pauta")
                f_link = st.text_input("Link de Referência")
                f_urg = st.select_slider("Urgência", ["Normal", "Programar", "URGENTE"])
                f_obs = st.text_area("Instruções")
                if st.form_submit_button("🚀 ENVIAR PARA FILA"):
                    conn = get_conn(); c = conn.cursor()
                    c.execute("INSERT INTO pautas_trabalho (titulo, link_ref, status, data_envio, prioridade, observacao) VALUES (?,?,'Pendente',?,?,?)",
                              (f_tit, f_link, datetime.now().strftime("%H:%M"), f_urg, f_obs))
                    conn.commit(); conn.close(); st.success("Enviado!"); st.rerun()
            
            st.markdown("---")
            st.subheader("📋 Status da Fila")
            conn = get_conn(); c = conn.cursor()
            c.execute("SELECT id, titulo, prioridade, status FROM pautas_trabalho ORDER BY id DESC LIMIT 5")
            for pid, ptit, pprio, pstat in c.fetchall():
                col_a, col_b = st.columns([4, 1])
                col_a.write(f"**{ptit}** ({pprio}) - {pstat}")
                if col_b.button("Remover", key=f"del_p_{pid}"):
                    c.execute("DELETE FROM pautas_trabalho WHERE id=?", (pid,))
                    conn.commit(); st.rerun()
            conn.close()

        with tab3:
            st.subheader("📅 Gestão da Agenda")
            col_cad, col_ver = st.columns([1, 2])
            with col_cad:
                with st.form("add_agenda"):
                    d_data = st.date_input("Data do Evento", format="DD/MM/YYYY")
                    d_txt = st.text_area("O que acontecerá?")
                    if st.form_submit_button("ADICIONAR À AGENDA"):
                        conn = get_conn(); c = conn.cursor()
                        c.execute("INSERT INTO agenda (dia, pauta) VALUES (?,?)", (d_data.strftime("%d/%m/%Y"), d_txt))
                        conn.commit(); conn.close(); st.rerun()
            
            with col_ver:
                conn = get_conn(); c = conn.cursor()
                c.execute("SELECT id, dia, pauta FROM agenda ORDER BY id DESC")
                for aid, adia, apau in c.fetchall():
                    with st.container(border=True):
                        st.markdown(f"<span class='data-agenda'>🗓️ {adia}</span>", unsafe_allow_html=True)
                        st.write(apau)
                        if st.button("Excluir", key=f"del_a_{aid}"):
                            c.execute("DELETE FROM agenda WHERE id=?", (aid,))
                            conn.commit(); st.rerun()
                conn.close()

    else:
        # PAINEL BRAYAN
        st.markdown('<div class="boas-vindas">Painel do Brayan</div>', unsafe_allow_html=True)
        t_b1, t_b2 = st.tabs(["🚀 MINHA FILA", "📅 AGENDA DO MÊS"])
        
        with t_b1:
            conn = get_conn(); c = conn.cursor()
            c.execute("SELECT id, titulo, link_ref, prioridade, observacao, data_envio FROM pautas_trabalho WHERE status='Pendente' ORDER BY id DESC")
            pautas = c.fetchall()
            if not pautas: st.success("Nenhuma pauta pendente!")
            for b_id, b_tit, b_link, b_prio, b_obs, b_h in pautas:
                cor = "card-urgente" if b_prio == "URGENTE" else "card-programar" if b_prio == "Programar" else ""
                st.markdown(f'<div class="card-pauta {cor}"><b>{b_prio}</b> | Enviado às {b_h} <br><h2 style="margin:5px 0;">{b_tit}</h2></div>', unsafe_allow_html=True)
                if b_obs: st.info(f"💡 {b_obs}")
                if b_link: st.link_button("🔗 ABRIR MATÉRIA", b_link, use_container_width=True)
                if st.button("✅ CONCLUÍDO / POSTADO", key=f"ok_b_{b_id}", use_container_width=True, type="primary"):
                    c.execute("UPDATE pautas_trabalho SET status='Concluído' WHERE id=?", (b_id,))
                    conn.commit(); st.rerun()
            conn.close()

        with t_b2:
            conn = get_conn(); c = conn.cursor()
            c.execute("SELECT dia, pauta FROM agenda ORDER BY id DESC LIMIT 20")
            for d, p in c.fetchall():
                st.markdown(f'<div class="card-agenda"><span class="data-agenda">📅 {d}</span>{p}</div>', unsafe_allow_html=True)
            conn.close()

    with st.sidebar:
        st.write(f"**Usuário:** {st.session_state.perfil.upper()}")
        if st.button("🚪 SAIR"):
            st.session_state.autenticado = False
            st.rerun()
