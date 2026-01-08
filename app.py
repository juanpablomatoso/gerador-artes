import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os

# Configuração da página
st.set_page_config(page_title="Painel Destaque Toledo", layout="wide", page_icon="📸")

# --- ESTILIZAÇÃO CSS AVANÇADA ---
st.markdown("""
    <style>
    /* Fundo e Fonte Geral */
    .main { background-color: #f8f9fa; }
    
    /* Botões da Lista de Notícias (Alinhados à Esquerda) */
    .stButton>button {
        width: 100%;
        text-align: left !important;
        border-radius: 8px !important;
        border: 1px solid #e0e0e0 !important;
        background-color: white !important;
        padding: 12px !important;
        color: #333 !important;
        font-weight: 500 !important;
        transition: all 0.3s ease;
        line-height: 1.4;
    }
    .stButton>button:hover {
        border-color: #007bff !important;
        background-color: #f0f7ff !important;
        transform: translateX(5px);
    }

    /* Cores dos Botões de Ação Principal */
    div[data-testid="stColumn"]:nth-of-type(1) button {
        background-color: #007bff !important; /* Azul Feed */
        color: white !important;
        font-weight: bold !important;
        text-align: center !important;
    }
    div[data-testid="stColumn"]:nth-of-type(2) button {
        background-color: #6f42c1 !important; /* Roxo Story */
        color: white !important;
        font-weight: bold !important;
        text-align: center !important;
    }

    /* Container do Manual */
    .instrucoes {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* Centralizar Logo */
    .logo-container {
        display: flex;
        justify-content: center;
        padding: 20px;
        background-color: white;
        margin-bottom: 25px;
        border-radius: 0 0 20px 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURAÇÕES DE CAMINHOS ---
CAMINHO_FONTE = "Shoika Bold.ttf"
TEMPLATE_FEED = "template_feed.png"
TEMPLATE_STORIE = "template_storie.png"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# --- FUNÇÕES CORE ---
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
    except:
        return []

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
    except:
        return None, None

# --- HEADER COM LOGO ---
st.markdown('<div class="logo-container"><img src="https://www.destaquetoledo.com.br/images/logo.png" width="300"></div>', unsafe_allow_html=True)

# --- CONTEÚDO ---
with st.expander("📘 Guia de Operação para a Equipe"):
    st.write("1. Escolha a notícia na lista à esquerda (os títulos estão alinhados para facilitar a leitura).")
    st.write("2. Verifique o link no campo central.")
    st.write("3. Use o botão **AZUL** para post de Feed ou o **ROXO** para Stories.")
    st.write("4. O botão de download aparecerá logo abaixo da imagem gerada.")

col_lista, col_trabalho = st.columns([1, 1.8])

with col_lista:
    st.subheader("📰 Notícias Recentes")
    if st.button("🔄 Atualizar Portal"):
        st.rerun()
    
    lista = obter_lista_noticias()
    for item in lista:
        # Botões agora alinhados à esquerda via CSS
        if st.button(item['titulo'], key=item['url']):
            st.session_state.url_ativa = item['url']

with col_trabalho:
    url_ativa = st.text_input("🔗 Link em Processamento:", value=st.session_state.get('url_ativa', ''))
    
    if url_ativa:
        st.divider()
        c1, c2 = st.columns(2)
        
        with c1:
            if st.button("🖼️ GERAR ARTE FEED"):
                with st.spinner("Processando..."):
                    img, tit = processar_artes_web(url_ativa, "FEED")
                    if img:
                        st.image(img, use_container_width=True)
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG", quality=95)
                        st.download_button("📥 Baixar Feed", buf.getvalue(), f"feed_{tit[:10]}.jpg", "image/jpeg")

        with c2:
            if st.button("📱 GERAR ARTE STORY"):
                with st.spinner("Processando..."):
                    img, tit = processar_artes_web(url_ativa, "STORY")
                    if img:
                        st.image(img, width=280)
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG", quality=95)
                        st.download_button("📥 Baixar Story", buf.getvalue(), f"story_{tit[:10]}.jpg", "image/jpeg")
    else:
        st.info("👈 Selecione uma matéria na lista lateral para iniciar a criação.")
