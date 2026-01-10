import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os

# --- 1. CONFIGURAÇÃO DA PÁGINA (Sempre o primeiro comando) ---
st.set_page_config(
    page_title="Destaque Toledo - Hub Profissional",
    layout="wide",
    page_icon="⚡"
)

# --- 2. ESTILO CSS GLOBAL (UI/UX PREMIUM) ---
st.markdown("""
    <style>
    /* Estilização da Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0e1117;
        border-right: 1px solid #30363d;
    }
    
    /* Cards de Notícias na Lista */
    .stButton>button {
        width: 100%;
        text-align: left !important;
        border-radius: 8px !important;
        padding: 10px 15px !important;
        margin-bottom: 5px;
    }

    /* Título das Páginas */
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1E1E1E;
        margin-bottom: 20px;
        border-left: 8px solid #007bff;
        padding-left: 15px;
    }

    /* Banner de Boas Vindas */
    .welcome-card {
        background: linear-gradient(135deg, #004a99 0%, #007bff 100%);
        color: white;
        padding: 40px;
        border-radius: 20px;
        margin-bottom: 30px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CONFIGURAÇÕES TÉCNICAS E FUNÇÕES DE ARTE ---
CAMINHO_FONTE = "Shoika Bold.ttf"
TEMPLATE_FEED = "template_feed.png"
TEMPLATE_STORIE = "template_storie.png"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

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
            while tam > 20:
                fnt = ImageFont.truetype(CAMINHO_FONTE, tam)
                lns = textwrap.wrap(titulo, width=int(662/(fnt.getlength("W")*0.55)))
                if (len(lns)*tam) <= 165 and len(lns) <= 3: break
                tam -= 1
            y = 811 - ((len(lns)*tam)//2)
            for l in lns:
                draw.text((488 - (draw.textbbox((0,0), l, font=fnt)[2]//2), y), l, fill="black", font=fnt)
                y += tam + 4
            return img_f.convert("RGB"), titulo
        else: # STORY
            L_S, A_S = 940, 541
            ratio = L_S / A_S
            ns_l, ns_a = (int(A_S*prop_o), A_S) if prop_o > ratio else (L_S, int(L_S/prop_o))
            img_s = img_original.resize((ns_l, ns_a), Image.LANCZOS).crop(((ns_l-L_S)//2, (ns_a-A_S)//2, (ns_l-L_S)//2+L_S, (ns_a-A_S)//2+A_S))
            canvas = Image.new("RGBA", (1080, 1920), (0,0,0,0))
            canvas.paste(img_s, (69, 504))
            if os.path.exists(TEMPLATE_STORIE):
                canvas.alpha_composite(Image.open(TEMPLATE_STORIE).convert("RGBA").resize((1080, 1920)))
            draw = ImageDraw.Draw(canvas)
            tam = 60
            while tam > 20:
                fnt = ImageFont.truetype(CAMINHO_FONTE, tam)
                lns = textwrap.wrap(titulo, width=int(912/(fnt.getlength("W")*0.55)))
                if (len(lns)*tam) <= 300 and len(lns) <= 4: break
                tam -= 2
            y = 1079
            for l in lns:
                draw.text((69, y), l, fill="white", font=fnt)
                y += tam + 12
            return canvas.convert("RGB"), titulo
    except: return None, None

# --- 4. DEFINIÇÃO DAS PÁGINAS ---

def pagina_dashboard():
    st.markdown('<div class="welcome-card"><h1>Bem-vindo ao Painel de Controle</h1><p>Selecione uma ferramenta no menu lateral para começar.</p></div>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Notícias Hoje", "12", "+2")
    c2.metric("Artes Geradas", "145", "Disponível")
    c3.metric("Status do Site", "Online", "Ping: 24ms")

def pagina_gerador_artes():
    st.markdown('<div class="main-title">Gerador Automático de Artes</div>', unsafe_allow_html=True)
    
    col_lista, col_trabalho = st.columns([1, 1.8])
    
    with col_lista:
        st.subheader("📰 Notícias Recentes")
        if st.button("🔄 Sincronizar"): st.rerun()
        
        lista = obter_lista_noticias()
        for item in lista:
            if st.button(item['titulo'], key=f"btn_{item['url']}"):
                st.session_state.url_ativa = item['url']

    with col_trabalho:
        url_ativa = st.text_input("📍 Link da Notícia Selecionada:", value=st.session_state.get('url_ativa', ''))
        
        if url_ativa:
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🖼️ GERAR FEED (Quadrado)", use_container_width=True):
                    img, tit = processar_artes_web(url_ativa, "FEED")
                    if img:
                        st.image(img, use_container_width=True)
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG")
                        st.download_button("📥 Baixar Feed", buf.getvalue(), "feed.jpg", "image/jpeg", use_container_width=True)
            with c2:
                if st.button("📱 GERAR STORY (Vertical)", use_container_width=True):
                    img, tit = processar_artes_web(url_ativa, "STORY")
                    if img:
                        st.image(img, width=250)
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG")
                        st.download_button("📥 Baixar Story", buf.getvalue(), "story.jpg", "image/jpeg", use_container_width=True)
        else:
            st.info("👈 Selecione uma notícia na lista ao lado para começar o design.")

def pagina_financeiro():
    st.markdown('<div class="main-title">Controle Financeiro</div>', unsafe_allow_html=True)
    st.info("Módulo em desenvolvimento. Aqui você poderá gerenciar anúncios e receitas.")

# --- 5. NAVEGAÇÃO LATERAL (O BOTÃO DO PAINEL) ---

with st.sidebar:
    st.title("🛡️ Sistema Destaque")
    st.divider()
    
    # Sistema de navegação por Radio (Visual de Botões)
    pagina_selecionada = st.radio(
        "MENU PRINCIPAL",
        ["🏠 Início / Dashboard", "📸 Gerador de Artes", "💰 Financeiro / Publi"],
        index=0
    )
    
    st.v_spacer(size=10)
    st.sidebar.markdown("---")
    st.caption("Versão 2.0.1 - 2024")

# --- 6. ROTEAMENTO DE PÁGINAS ---
if pagina_selecionada == "🏠 Início / Dashboard":
    pagina_dashboard()
elif pagina_selecionada == "📸 Gerador de Artes":
    pagina_gerador_artes()
elif pagina_selecionada == "💰 Financeiro / Publi":
    pagina_financeiro()
