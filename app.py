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

    # tabela antiga (mantida)
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS agenda (
            dia TEXT PRIMARY KEY,
            pauta TEXT
        )
        """
    )

    # pautas do Brayan
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS pautas_trabalho (
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

    # agenda nova
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS agenda_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_ref TEXT NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT,
            status TEXT NOT NULL DEFAULT 'Pendente',
            criado_por TEXT,
            criado_em TEXT
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
                    st.session_state["login_em"] = datetime.utcnow().timestamp()
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

        with tab1:
            st.markdown(
                '<p class="descricao-aba">Aqui você gera automaticamente os posts para Instagram.</p>',
                unsafe_allow_html=True,
            )
            c1, col_preview = st.columns([1, 2])

            with c1:
                st.subheader("📰 Notícias Recentes")
                ultimas = buscar_ultimas()
                if not ultimas:
                    st.info("Não foi possível carregar as notícias agora.")
                for i, item in enumerate(ultimas):
                    if st.button(item["t"], key=f"btn_{i}", use_container_width=True):
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
                            img.save(buf, "JPEG", quality=95, optimize=True)
                            st.download_button(
                                "📥 BAIXAR FEED",
                                buf.getvalue(),
                                "feed.jpg",
                                use_container_width=True,
                            )
                        except Exception as e:
                            st.error(f"Falha ao gerar FEED: {e}")

                    if cb.button("📱 GERAR STORY", use_container_width=True):
                        try:
                            img = processar_artes_integrado(url_f, "STORY")
                            st.image(img, width=280)

                            buf = io.BytesIO()
                            img.save(buf, "JPEG", quality=95, optimize=True)
                            st.download_button(
                                "📥 BAIXAR STORY",
                                buf.getvalue(),
                                "story.jpg",
                                use_container_width=True,
                            )
                        except Exception as e:
                            st.error(f"Falha ao gerar STORY: {e}")

        with tab2:
            st.markdown(
                '<p class="descricao-aba">Envie as matérias que o Brayan deve postar.</p>',
                unsafe_allow_html=True,
            )
            with st.form("form_envio_colorido"):
                f_titulo = st.text_input("Título da Matéria")
                f_link = st.text_input("Link da Matéria")
                f_obs = st.text_area("Instruções para o Brayan")
                f_urgencia = st.select_slider("Nível de Prioridade", options=["Normal", "Programar", "URGENTE"])

                if st.form_submit_button("🚀 ENVIAR PARA O BRAYAN", use_container_width=True):
                    if f_titulo:
                        hora_br = (datetime.utcnow() - timedelta(hours=3)).strftime("%H:%M")
                        conn = get_conn()
                        c = conn.cursor()
                        c.execute(
                            """
                            INSERT INTO pautas_trabalho
                            (titulo, link_ref, status, data_envio, prioridade, observacao)
                            VALUES (?,?,'Pendente',?,?,?)
                            """,
                            (f_titulo, f_link, hora_br, f_urgencia, f_obs),
                        )
                        conn.commit()
                        conn.close()
                        st.success("Pauta enviada!")
                        st.rerun()
                    else:
                        st.warning("Informe ao menos o título.")

            st.markdown("---")
            st.subheader("📋 Últimos Envios")
            conn = get_conn()
            c = conn.cursor()
            c.execute("SELECT id, titulo, prioridade, data_envio, status FROM pautas_trabalho ORDER BY id DESC LIMIT 6")
            p_hist = c.fetchall()
            conn.close()

            cols_hist = st.columns(3)
            for i, p in enumerate(p_hist):
                with cols_hist[i % 3]:
                    classe_cor = "card-urgente" if p[2] == "URGENTE" else "card-programar" if p[2] == "Programar" else ""
                    st.markdown(
                        f"<div class='card-pauta {classe_cor}'><small>{p[3]}</small><br><b>{p[1]}</b></div>",
                        unsafe_allow_html=True,
                    )
                    if st.button("Remover", key=f"ex_{p[0]}"):
                        conn = get_conn()
                        c = conn.cursor()
                        c.execute("DELETE FROM pautas_trabalho WHERE id=?", (p[0],))
                        conn.commit()
                        conn.close()
                        st.rerun()

        # ============================================================
        # 📅 ABA AGENDA - VERSÃO PROFISSIONAL (FOCO SEMANAL)
        # ============================================================
        with tab3:
            st.markdown('<p class="descricao-aba">Planejamento Editorial - Exibindo automaticamente os próximos 7 dias e pendências.</p>', unsafe_allow_html=True)

            conn = get_conn()
            hoje_dt = (datetime.utcnow() - timedelta(hours=3)).date()
            fim_semana = hoje_dt + timedelta(days=7)

            # --- 1) INPUT DE NOVA TAREFA ---
            with st.form("form_agenda_nova_v3"):
                st.markdown("#### ✨ Novo Compromisso")
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    a_titulo = st.text_input("Título")
                    a_desc = st.text_area("Observações", height=65)
                with col_b:
                    a_data = st.date_input("Data", value=hoje_dt, format="DD/MM/YYYY")
                    a_status = st.selectbox("Status", ["Pendente", "Concluído"])
                
                if st.form_submit_button("➕ AGENDAR", use_container_width=True, type="primary"):
                    if a_titulo:
                        agora_str = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
                        c = conn.cursor()
                        c.execute(
                            "INSERT INTO agenda_itens (data_ref, titulo, descricao, status, criado_por, criado_em) VALUES (?, ?, ?, ?, ?, ?)",
                            (a_data.strftime("%Y-%m-%d"), a_titulo, a_desc, a_status, st.session_state.perfil, agora_str)
                        )
                        conn.commit()
                        st.rerun()

            st.markdown("---")
            st.subheader(f"📌 Próximos 7 Dias (até {fim_semana.strftime('%d/%m/%Y')})")

            # --- 2) LISTAGEM INTELIGENTE ---
            c = conn.cursor()
            c.execute(
                """
                SELECT id, data_ref, titulo, descricao, status, criado_por 
                FROM agenda_itens 
                WHERE (data_ref BETWEEN ? AND ?) OR (status = 'Pendente' AND data_ref < ?)
                ORDER BY status DESC, data_ref ASC
                """,
                (hoje_dt.strftime("%Y-%m-%d"), fim_semana.strftime("%Y-%m-%d"), hoje_dt.strftime("%Y-%m-%d"))
            )
            itens = c.fetchall()

            if not itens:
                st.info("Nenhuma tarefa para os próximos 7 dias.")
            else:
                for (tid, data_ref, titulo, descricao, status, criado_por) in itens:
                    dt_obj = datetime.strptime(data_ref, "%Y-%m-%d").date()
                    data_br = dt_obj.strftime("%d/%m/%Y")
                    
                    if status == "Concluído":
                        cor, tag, fundo = "#198754", "✅ CONCLUÍDO", "#f1fff6"
                    elif dt_obj < hoje_dt:
                        cor, tag, fundo = "#dc3545", "⛔ ATRASADO", "#fff5f5"
                    elif dt_obj == hoje_dt:
                        cor, tag, fundo = "#ffc107", "📌 HOJE", "#fffdf5"
                    else:
                        cor, tag, fundo = "#0d6efd", "🗓️ PRÓXIMO", "#f3f7ff"

                    st.markdown(f"""
                        <div style="background:{fundo}; padding:12px; border-radius:10px; border-left:6px solid {cor}; margin-bottom:10px;">
                            <small>{data_br} — <b>{tag}</b> | Por: {criado_por.upper()}</small><br>
                            <span style="font-size:1.1rem; font-weight:bold;">{titulo}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    if descricao:
                        st.caption(f"📝 {descricao}")

                    b1, b2, _ = st.columns([0.8, 0.8, 4])
                    if b1.button("✅/↩", key=f"tgl_{tid}"):
                        novo_st = "Pendente" if status == "Concluído" else "Concluído"
                        c.execute("UPDATE agenda_itens SET status=? WHERE id=?", (novo_st, tid))
                        conn.commit()
                        st.rerun()
                    if b2.button("🗑️", key=f"exc_{tid}"):
                        c.execute("DELETE FROM agenda_itens WHERE id=?", (tid,))
                        conn.commit()
                        st.rerun()
            conn.close()

    else:
        # ============================================================
        # PAINEL BRAYAN
        # ============================================================
        st.markdown('<div class="boas-vindas">Olá, Brayan! Bom trabalho.</div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="descricao-aba">Confira abaixo as matérias enviadas pelo Juan.</p>',
            unsafe_allow_html=True,
        )

        conn = get_conn()
        c = conn.cursor()
        c.execute(
            """
            SELECT id, titulo, link_ref, data_envio, prioridade, observacao
            FROM pautas_trabalho
            WHERE status = 'Pendente'
            ORDER BY id DESC
            """
        )
        p_br = c.fetchall()
        conn.close()

        if not p_br:
            st.success("Tudo em dia! Nenhuma pauta nova por enquanto.")

        for pb in p_br:
            b_id, b_tit, b_link, b_hora, b_prio, b_obs = pb
            classe_cor = "card-urgente" if b_prio == "URGENTE" else "card-programar" if b_prio == "Programar" else ""
            tag_cor = "tag-urgente" if b_prio == "URGENTE" else "tag-programar" if b_prio == "Programar" else "tag-normal"

            st.markdown(
                f"""
                <div class="card-pauta {classe_cor}">
                    <span class="tag-status {tag_cor}">{b_prio}</span> | 🕒 {b_hora}<br>
                    <p style='font-size: 1.4rem; font-weight: bold; margin: 10px 0;'>{b_tit}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if b_obs:
                st.markdown(
                    f'<div class="obs-box"><b>💡 Instrução do Juan:</b><br>{b_obs}</div>',
                    unsafe_allow_html=True,
                )

            if b_link and b_link != "Sem Link":
                st.link_button("🔗 ABRIR MATÉRIA NO SITE", b_link, use_container_width=True)

            st.write("")

            if st.button("✅ MARCAR COMO POSTADO", key=f"ok_{b_id}", use_container_width=True, type="primary"):
                conn = get_conn()
                c = conn.cursor()
                c.execute("UPDATE pautas_trabalho SET status='✅ Concluído' WHERE id=?", (b_id,))
                conn.commit()
                conn.close()
                st.rerun()

            st.markdown("---")

        # =========================
        # ✅ AGENDA TAMBÉM PARA O BRAYAN (VER + CADASTRAR + EDITAR + EXCLUIR)
        # =========================
        st.markdown("---")
        st.subheader("📅 Agenda Editorial (Brayan)")

        # Garante tabela
        conn = get_conn()
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS agenda_itens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_ref TEXT NOT NULL,
                titulo TEXT NOT NULL,
                descricao TEXT,
                status TEXT NOT NULL DEFAULT 'Pendente',
                criado_por TEXT,
                criado_em TEXT
            )
            """
        )
        conn.commit()
        conn.close()

        hoje_dt = (datetime.utcnow() - timedelta(hours=3)).date()

        col_f1, col_f2 = st.columns([1.2, 1])
        with col_f1:
            filtro_dt = st.date_input("Data de referência (agenda)", value=hoje_dt, key="br_ag_filtro_dt")
        with col_f2:
            visao = st.selectbox("Visualização (agenda)", ["Dia", "Semana", "Todas"], index=1, key="br_ag_visao")

        with st.form("form_agenda_nova_brayan"):
            col_a, col_b = st.columns([1.3, 1])
            with col_a:
                a_titulo = st.text_input("Título da tarefa", key="br_ag_titulo")
                a_desc = st.text_area("Descrição (opcional)", height=90, key="br_ag_desc")
            with col_b:
                a_data = st.date_input("Data da tarefa", value=filtro_dt, key="br_ag_data")
                a_status = st.selectbox("Status", ["Pendente", "Concluído"], index=0, key="br_ag_status")

            if st.form_submit_button("➕ ADICIONAR À AGENDA", use_container_width=True):
                if a_titulo and a_data:
                    agora = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute(
                        """
                        INSERT INTO agenda_itens (data_ref, titulo, descricao, status, criado_por, criado_em)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            a_data.strftime("%Y-%m-%d"),
                            a_titulo,
                            a_desc,
                            a_status,
                            "brayan",
                            agora,
                        ),
                    )
                    conn.commit()
                    conn.close()
                    st.success("Tarefa adicionada.")
                    st.rerun()
                else:
                    st.warning("Informe pelo menos a data e o título.")

        st.markdown("---")

        filtro_params = []
        where = "1=1"

        if visao == "Dia":
            where += " AND data_ref = ?"
            filtro_params.append(filtro_dt.strftime("%Y-%m-%d"))
        elif visao == "Semana":
            dow = filtro_dt.weekday()
            start = filtro_dt - timedelta(days=dow)
            end = start + timedelta(days=6)
            where += " AND data_ref BETWEEN ? AND ?"
            filtro_params.extend([start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")])

        conn = get_conn()
        c = conn.cursor()
        c.execute(
            f"""
            SELECT id, data_ref, titulo, descricao, status, criado_por, criado_em
            FROM agenda_itens
            WHERE {where}
            ORDER BY data_ref ASC, id DESC
            """,
            tuple(filtro_params),
        )
        itens = c.fetchall()
        conn.close()

        if not itens:
            st.info("Nenhuma tarefa encontrada para o filtro selecionado.")
        else:
            hoje_iso = hoje_dt.strftime("%Y-%m-%d")

            for (tid, data_ref, titulo, descricao, status, criado_por, criado_em) in itens:
                if status == "Concluído":
                    borda = "#198754"
                    fundo = "#f1fff6"
                    tag = "✅ CONCLUÍDO"
                else:
                    if data_ref < hoje_iso:
                        borda = "#dc3545"
                        fundo = "#fff5f5"
                        tag = "⛔ ATRASADO"
                    elif data_ref == hoje_iso:
                        borda = "#ffc107"
                        fundo = "#fffdf5"
                        tag = "📌 HOJE"
                    else:
                        borda = "#0d6efd"
                        fundo = "#f3f7ff"
                        tag = "🗓️ PENDENTE"

                data_br = datetime.strptime(data_ref, "%Y-%m-%d").strftime("%d/%m/%Y")

                st.markdown(
                    f"""
                    <div style="background:{fundo}; padding:14px; border-radius:12px; border-left:6px solid {borda}; box-shadow:0 2px 8px rgba(0,0,0,0.05); margin-bottom:10px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
                            <div>
                                <div style="font-size:0.85rem; color:#555;"><b>{data_br}</b> • <span style="opacity:.9;">{tag}</span></div>
                                <div style="font-size:1.15rem; font-weight:700; color:#111; margin-top:4px;">{titulo}</div>
                            </div>
                            <div style="font-size:0.8rem; color:#666; text-align:right;">
                                <div>{(criado_por or "").upper()}</div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if descricao:
                    st.markdown(f"<div class='obs-box'>{descricao}</div>", unsafe_allow_html=True)

                col1, col2, col3, col4 = st.columns([1, 1, 1, 2])

                with col1:
                    if status == "Concluído":
                        if st.button("↩️ Reabrir", key=f"br_ag_reabrir_{tid}", use_container_width=True):
                            conn = get_conn()
                            c = conn.cursor()
                            c.execute("UPDATE agenda_itens SET status='Pendente' WHERE id=?", (tid,))
                            conn.commit()
                            conn.close()
                            st.rerun()
                    else:
                        if st.button("✅ Concluir", key=f"br_ag_concluir_{tid}", use_container_width=True):
                            conn = get_conn()
                            c = conn.cursor()
                            c.execute("UPDATE agenda_itens SET status='Concluído' WHERE id=?", (tid,))
                            conn.commit()
                            conn.close()
                            st.rerun()

                with col2:
                    if st.button("✏️ Editar", key=f"br_ag_editar_{tid}", use_container_width=True):
                        st.session_state[f"br_edit_ag_{tid}"] = True

                with col3:
                    if st.button("🗑️ Excluir", key=f"br_ag_excluir_{tid}", use_container_width=True):
                        conn = get_conn()
                        c = conn.cursor()
                        c.execute("DELETE FROM agenda_itens WHERE id=?", (tid,))
                        conn.commit()
                        conn.close()
                        st.rerun()

                if st.session_state.get(f"br_edit_ag_{tid}", False):
                    with st.form(f"form_edit_ag_br_{tid}"):
                        e1, e2 = st.columns([1.2, 1])
                        with e1:
                            novo_titulo = st.text_input("Título", value=titulo, key=f"br_edit_t_{tid}")
                            nova_desc = st.text_area("Descrição", value=(descricao or ""), height=90, key=f"br_edit_d_{tid}")
                        with e2:
                            nova_data = st.date_input("Data", value=datetime.strptime(data_ref, "%Y-%m-%d").date(), key=f"br_edit_dt_{tid}")
                            novo_status = st.selectbox(
                                "Status",
                                ["Pendente", "Concluído"],
                                index=0 if status == "Pendente" else 1,
                                key=f"br_edit_s_{tid}",
                            )

                        c_save, c_cancel = st.columns(2)
                        salvar = c_save.form_submit_button("💾 Salvar", use_container_width=True, type="primary")
                        cancelar = c_cancel.form_submit_button("Cancelar", use_container_width=True)

                        if salvar:
                            conn = get_conn()
                            c = conn.cursor()
                            c.execute(
                                """
                                UPDATE agenda_itens
                                SET data_ref=?, titulo=?, descricao=?, status=?
                                WHERE id=?
                                """,
                                (
                                    nova_data.strftime("%Y-%m-%d"),
                                    novo_titulo,
                                    nova_desc,
                                    novo_status,
                                    tid,
                                ),
                            )
                            conn.commit()
                            conn.close()
                            st.session_state[f"br_edit_ag_{tid}"] = False
                            st.rerun()

                        if cancelar:
                            st.session_state[f"br_edit_ag_{tid}"] = False
                            st.rerun()

                st.markdown("---")

        if st.button("🆘 Precisa de ajuda ou encontrou um erro?"):
            st.warning("Brayan, caso o sistema apresente erro, entre em contato direto com o Juan.")

    # ============================================================
    # SIDEBAR
    # ============================================================
    with st.sidebar:
        st.write(f"Logado como: **{st.session_state.perfil.upper()}**")
        if st.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state.autenticado = False
            st.rerun()




