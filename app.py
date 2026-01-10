import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os
from datetime import datetime

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Destaque Toledo - Hub Profissional",
    layout="wide",
    page_icon="⚡"
)

# --- 2. ESTILO CSS GLOBAL ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #0e1117; border-right: 1px solid #30363d; }
    .stButton>button { width: 100%; border-radius: 8px !important; }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #1E1E1E; border-left: 8px solid #007bff; padding-left: 15px; margin-bottom: 20px; }
    .welcome-card { background: linear-gradient(135deg, #004a99 0%, #007bff 100%); color: white; padding: 30px; border-radius: 20px; margin-bottom: 30px; }
    .publi-box { background: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CONFIGURAÇÕES E FUNÇÕES DE ARTE ---
CAMINHO_FONTE = "Shoika Bold.ttf"
TEMPLATE_FEED = "template_feed.png"
TEMPLATE_STORIE = "template_storie.png"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def obter_lista_noticias():
    try:
        url_site = "https://www.destaquetoledo.com.br/"
        res = requests.get(url_site, headers=HEADERS, timeout=10).text
        soup = BeautifulSoup(res, "html.parser")
        noticias = []
        for a in soup.find_all("a", href=True):
            href = a['href']
            if ".html" in href and "/20" in href and href not in [n['url'] for n in noticias]:
                titulo_limpo = a.get_text(strip=True)
                if len(titulo_limpo) > 15:
                    noticias.append({"titulo": titulo_limpo, "url": href})
        return noticias[:12]
    except: return []

def processar_artes_web(url, tipo_saida):
    try:
        res_m = requests.get(url, headers=HEADERS).text
        soup_m = BeautifulSoup(res_m, "html.parser")
        titulo = soup_m.find("h1").get_text(strip=True)
        corpo = soup_m.find(class_="post-body") or soup_m
        img_url = next(img.get("src") for img in corpo.find_all("img") if "logo" not in img.get("src").lower())
        img_res = requests.get(img_url, headers=HEADERS)
        img_original = Image.open(io.BytesIO(img_res.content)).convert("RGBA")
        
        larg_o, alt_o = img_original.size
        prop_o = larg_o / alt_o

        if tipo_saida == "FEED":
            TAM = 1000
            if prop_o > 1.0:
                n_alt = TAM
                n_larg = int(TAM * prop_o)
                img_f = img_original.resize((n_larg, n_alt), Image.LANCZOS).crop(((n_larg-TAM)//2, 0, (n_larg-TAM)//2+TAM, TAM))
            else:
                n_larg = TAM
                n_alt = int(TAM / prop_o)
                img_f = img_original.resize((n_larg, n_alt), Image.LANCZOS).crop((0, (n_alt-TAM)//2, TAM, (n_alt-TAM)//2+TAM))
            if os.path.exists(TEMPLATE_FEED):
                img_f.alpha_composite(Image.open(TEMPLATE_FEED).convert("RGBA").resize((TAM, TAM)))
            draw = ImageDraw.Draw(img_f)
            tam = 85
            fnt = ImageFont.truetype(CAMINHO_FONTE, tam) # Simplificado para o exemplo
            draw.text((50, 800), titulo[:40]+"...", fill="black", font=fnt)
            return img_f.convert("RGB"), titulo
        else: # STORY
            canvas = Image.new("RGBA", (1080, 1920), (0,0,0,0))
            # ... (Sua lógica de story original entra aqui)
            return canvas.convert("RGB"), titulo
    except: return None, None

# --- 4. DEFINIÇÃO DAS PÁGINAS ---

def pagina_dashboard():
    st.markdown('<div class="welcome-card"><h1>Painel Geral</h1><p>Bem-vindo ao sistema de gestão Destaque Toledo.</p></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Notícias", "Sincronizadas", "OK")
    c2.metric("Status", "Online", "2026")
    c3.metric("Publicidade", "4 Ativas", "Mensal")

def pagina_gerador_artes():
    st.markdown('<div class="main-title">Gerador de Artes</div>', unsafe_allow_html=True)
    col_lista, col_trabalho = st.columns([1, 1.8])
    with col_lista:
        st.subheader("📰 Recentes")
        lista = obter_lista_noticias()
        for item in lista:
            if st.button(item['titulo'], key=f"btn_{item['url']}"):
                st.session_state.url_ativa = item['url']
    with col_trabalho:
        url_ativa = st.text_input("📍 URL ativa:", value=st.session_state.get('url_ativa', ''))
        if url_ativa:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🖼️ GERAR FEED"):
                    img, _ = processar_artes_web(url_ativa, "FEED")
                    if img: st.image(img, use_container_width=True)
            with c2:
                if st.button("📱 GERAR STORY"):
                    img, _ = processar_artes_web(url_ativa, "STORY")
                    if img: st.image(img, width=250)

def pagina_agenda_semanal():
    st.markdown('<div class="main-title">📅 Agenda Fixa da Semana</div>', unsafe_allow_html=True)
    dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    cols = st.columns(7)
    for i, dia in enumerate(dias):
        with cols[i]:
            st.info(f"**{dia}**")
            key = f"agenda_{dia}"
            if key not in st.session_state: st.session_state[key] = ""
            st.session_state[key] = st.text_area("Pauta:", value=st.session_state[key], key=f"ta_{dia}", height=150)
    st.button("💾 Salvar Agenda (Sessão)")

def pagina_publicidade():
    st.markdown('<div class="main-title">📢 Stories de Publicidade</div>', unsafe_allow_html=True)
    
    # Exemplo de empresas (Aqui você cadastra suas publis)
    publis = {
        "Supermercado Toledo": {"user": "@supertoledo", "link": "https://ofertas.com", "banner": "https://via.placeholder.com/1080x1920/004a99/ffffff?text=OFERTAS+DO+DIA"},
        "Farmácia Saúde": {"user": "@farmasaude", "link": "https://wa.me/123", "banner": "https://via.placeholder.com/1080x1920/cc0000/ffffff?text=PROMO+SAUDE"},
    }
    
    sel = st.selectbox("Escolha a Empresa:", list(publis.keys()))
    dados = publis[sel]
    
    col_info, col_banner = st.columns([1, 1.5])
    with col_info:
        st.markdown(f"""
        <div class="publi-box">
            <h3>{sel}</h3>
            <p><b>Marcar:</b> {dados['user']}</p>
            <p><b>Link:</b> {dados['link']}</p>
        </div>
        """, unsafe_allow_html=True)
        st.code(f"{dados['user']}\n{dados['link']}")
        st.button("Copiar p/ Celular")
    
    with col_banner:
        st.image(dados['banner'], width=300)

def pagina_artes_prontas():
    st.markdown('<div class="main-title">🖼️ Artes Prontas</div>', unsafe_allow_html=True)
    artes = [
        {"nome": "Bom Dia", "img": "https://via.placeholder.com/300x500?text=BOM+DIA"},
        {"nome": "Plantão", "img": "https://via.placeholder.com/300x500?text=PLANTAO"},
        {"nome": "Luto", "img": "https://via.placeholder.com/300x500?text=LUTO"}
    ]
    cols = st.columns(4)
    for i, arte in enumerate(artes):
        with cols[i % 4]:
            st.image(arte['img'], use_container_width=True)
            st.download_button(f"Baixar {arte['nome']}", b"data", file_name=f"{arte['nome']}.jpg")

# --- 5. NAVEGAÇÃO LATERAL ---
with st.sidebar:
    st.title("🛡️ DESTAQUE PRO")
    st.divider()
    pagina_selecionada = st.radio(
        "MENU PRINCIPAL",
        ["🏠 Dashboard", "📸 Gerador de Artes", "📅 Agenda Semanal", "📢 Publicidade", "🖼️ Artes Prontas"],
        index=0
    )
    st.divider()
    st.caption(f"v2.5 | 2026")

# --- 6. ROTEAMENTO ---
if pagina_selecionada == "🏠 Dashboard": pagina_dashboard()
elif pagina_selecionada == "📸 Gerador de Artes": pagina_gerador_artes()
elif pagina_selecionada == "📅 Agenda Semanal": pagina_agenda_semanal()
elif pagina_selecionada == "📢 Publicidade": pagina_publicidade()
elif pagina_selecionada == "🖼️ Artes Prontas": pagina_artes_prontas()
