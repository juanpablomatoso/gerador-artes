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
#    Preferência:
#      A) st.secrets["AUTH"] no Streamlit Cloud / secrets.toml
#      B) variáveis de ambiente DT_AUTH_JUAN / DT_AUTH_BRAYAN
#
#    Formato da senha armazenada: "pbkdf2_sha256$iterations$salt_hex$hash_hex"
#
#    Para gerar, você pode usar a função abaixo (rode localmente no Python):
#      print(make_password_hash("sua_senha"))
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
    # 1) tenta secrets
    auth = {}
    try:
        if "AUTH" in st.secrets:
            auth = dict(st.secrets["AUTH"])
    except Exception:
        auth = {}

    # 2) fallback env vars
    juan_hash = auth.get("juan") or os.getenv("DT_AUTH_JUAN", "").strip()
    brayan_hash = auth.get("brayan") or os.getenv("DT_AUTH_BRAYAN", "").strip()

    return {
        "juan": juan_hash,
        "brayan": brayan_hash,
    }

AUTH_HASHES = load_auth_hashes()

# Se o usuário não configurou as hashes, o sistema não autentica.
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
    c.execute("CREATE TABLE IF NOT EXISTS agenda (dia TEXT PRIMARY KEY, pauta TEXT)")
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
def get_requests_session(headers_key: str):
    s = requests.Session()
    s.headers.update(HEADERS)
    return s

SESSION = get_requests_session(str(HEADERS))

def safe_get_text(url: str) -> str:
    r = SESSION.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    # tenta respeitar encoding do servidor
    if r.encoding is None:
        r.encoding = "utf-8"
    return r.text

def safe_get_bytes(url: str) -> bytes:
    r = SESSION.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.content

# ============================================================
# 7) SCRAPING + ARTE (ROBUSTO)
# ============================================================
def extrair_titulo(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        t = h1.get_text(" ", strip=True)
        if t:
            return t
    # fallback: title do HTML
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    return "Sem título"

def normalizar_url(base: str, candidate: str) -> str:
    if not candidate:
        return ""
    return urljoin(base, candidate)

def encontrar_primeira_imagem_util(base_url: str, soup: BeautifulSoup) -> str:
    # tenta priorizar área de conteúdo
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
        # filtros simples
        if "logo" in low or "icon" in low or "sprite" in low:
            continue
        if not re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", low):
            # às vezes o site serve sem extensão; mantém como candidato, mas com menor prioridade
            candidatos.append(full)
            continue

        # imagem com extensão tem prioridade
        return full

    # se não achou com extensão, tenta o primeiro candidato que sobrou
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

        # Ajuste/crop para 1000x1000 preservando centro
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

        # Ajuste de fonte para caber no bloco (mesma lógica, com proteções)
        tam = 85
        while tam > 20:
            fonte = ImageFont.truetype(CAMINHO_FONTE, tam)
            # getlength pode variar; mantém seu cálculo base
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
for article in soup.find_all("article"):
    a = article.find("a", href=True)
    if not a:
        continue

    href = a["href"].strip()
    titulo = a.get_text(" ", strip=True)

    if titulo and len(titulo) > 25:
        news.append({
            "t": titulo,
            "u": urljoin(base, href)
        })

        # remove duplicados por URL
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
# 9) LOGIN (SEM HARDCODE + MENSAGEM SE CONFIG FALTANDO)
# ============================================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown(
        '<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1><p>Painel Administrativo</p></div>',
        unsafe_allow_html=True,
    )
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        if not AUTH_CONFIG_OK:
            st.error(
                "Autenticação não configurada.\n\n"
                "Você precisa definir as senhas em HASH.\n"
                "Opções:\n"
                "1) Variáveis de ambiente: DT_AUTH_JUAN e DT_AUTH_BRAYAN\n"
                "2) Streamlit secrets: [AUTH] juan=... brayan=...\n\n"
                "Formato: pbkdf2_sha256$iterations$salt_hex$hash_hex"
            )
            st.stop()

        with st.form("login_direto"):
            u = st.text_input("Usuário").lower().strip()
            s = st.text_input("Senha", type="password")

            if st.form_submit_button("ENTRAR NO SISTEMA", use_container_width=True):
                if u in ("juan", "brayan") and verify_password(s, AUTH_HASHES.get(u, "")):
                    st.session_state.autenticado = True
                    st.session_state.perfil = u
                    st.rerun()
                else:
                    st.error("Acesso negado.")

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

        with tab3:
            st.info("A aba AGENDA está mantida como no seu projeto (tabela 'agenda'). Se quiser, posso finalizar a UI dela.")

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



