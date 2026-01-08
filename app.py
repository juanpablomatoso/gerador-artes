import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os

# Configuração da página
st.set_page_config(page_title="Painel Destaque Toledo", layout="wide", page_icon="📸")

# --- ESTILIZAÇÃO CSS PROFISSIONAL ---
st.markdown("""
    <style>
    /* Fundo do App */
    .main { background-color: #f4f7f9; }
    
    /* Cabeçalho de Texto Estilizado */
    .header-container {
        text-align: center;
        padding: 30px;
        background: linear-gradient(135deg, #004a99 0%, #007bff 100%);
        color: white;
        border-radius: 0 0 25px 25px;
        margin-bottom: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .header-title { font-size: 32px; font-weight: 800; letter-spacing: 1px; margin: 0; }
    .header-subtitle { font-size: 14px; opacity: 0.9; font-weight: 300; }

    /* Botões da Lista de Notícias (Alinhados à Esquerda) */
    .stButton>button {
        width: 100%;
        text-align: left !important;
        border-radius: 10px !important;
        border: none !important;
        background-color: white !important;
        padding: 15px !important;
        color: #2c3e50 !important;
        font-weight: 500 !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
        transition: all 0.2s ease;
        margin-bottom: 5px;
    }
    .stButton>button:hover {
        background-color: #eef6ff !important;
        color: #007bff !important;
        transform: scale(1.02);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1) !important;
    }

    /* Estilo dos Botões de Ação Principal (Feed e Story) */
    div[data-testid="stColumn"]:nth-of-type(1) button {
        background: #007bff !important; /* Azul Royal */
        color: white !important;
        text-align: center !important;
        font-weight: bold !important;
        height: 50px;
    }
    div[data-testid="stColumn"]:nth-of-type(2) button {
        background: #6610f2 !important; /* Roxo Intenso */
        color: white !important;
        text-align: center !important;
        font-weight: bold !important;
        height: 50px;
    }
    
    /* Área de Preview */
    .preview-box {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #e1e8ed;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURAÇÕES DE CAMINHOS ---
CAMINHO_FONTE = "Shoika Bold.ttf"
TEMPLATE_FEED = "template_feed.png"
TEMPLATE_STORIE = "template_storie.png"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# --- FUNÇÕES DE BUSCA E PROCESSAMENTO ---
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

# --- CABEÇALHO PERSONALIZADO ---
st.markdown("""
    <div class="header-container">
        <h1 class="header-title">PAINEL DE PRODUÇÃO</h1>
        <p class="header-subtitle">CENTRAL DE ARTES AUTOMÁTICAS | DESTAQUE TOLEDO</p>
    </div>
    """, unsafe_allow_html=True)

# --- LAYOUT PRINCIPAL ---
col_lista, col_trabalho = st.columns([1, 1.8])

with col_lista:
    st.markdown("### 📰 Notícias Recentes")
    if st.button("🔄 Atualizar Lista do Site"):
        st.rerun()
    
    lista = obter_lista_noticias()
    if not lista:
        st.info("Nenhuma notícia nova encontrada.")
    for item in lista:
        if st.button(item['titulo'], key=item['url']):
            st.session_state.url_ativa = item['url']

with col_trabalho:
    url_ativa = st.text_input("🔗 Matéria em Edição:", value=st.session_state.get('url_ativa', ''))
    
    if url_ativa:
        st.markdown('<div class="preview-box">', unsafe_allow_html=True)
        st.markdown("### 🎨 Criar Conteúdo")
        c1, c2 = st.columns(2)
        
        with c1:
            if st.button("🖼️ GERAR POST FEED"):
                with st.spinner("Criando arte quadrada..."):
                    img, tit = processar_artes_web(url_ativa, "FEED")
                    if img:
                        st.image(img, use_container_width=True)
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG", quality=95)
                        st.download_button("📥 Baixar Feed", buf.getvalue(), f"feed_{tit[:10]}.jpg", "image/jpeg")
                        st.success("Pronto para postar!")

        with c2:
            if st.button("📱 GERAR STORY"):
                with st.spinner("Criando arte vertical..."):
                    img, tit = processar_artes_web(url_ativa, "STORY")
                    if img:
                        st.image(img, width=280)
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG", quality=95)
                        st.download_button("📥 Baixar Story", buf.getvalue(), f"story_{tit[:10]}.jpg", "image/jpeg")
                        st.success("Pronto para os stories!")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.warning("👈 Selecione uma notícia na lista ao lado para começar.")
