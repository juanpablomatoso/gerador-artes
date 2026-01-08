import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os

# Configurações iniciais
st.set_page_config(page_title="Gerador Destaque", page_icon="🎨")

# --- CONFIGURAÇÕES DE ARQUIVOS (Agora relativos ao GitHub) ---
CAMINHO_FONTE = "Shoika Bold.ttf"
TEMPLATE_FEED = "template_feed.png"
TEMPLATE_STORIE = "template_storie.png"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def processar_imagem_web(url, tipo_arte):
    # Faz o download da matéria
    res_m = requests.get(url, headers=HEADERS).text
    soup_m = BeautifulSoup(res_m, "html.parser")
    titulo = soup_m.find("h1").get_text(strip=True)
    corpo = soup_m.find(class_="post-body") or soup_m
    img_url = next(img.get("src") for img in corpo.find_all("img") if "logo" not in img.get("src").lower())
    
    img_res = requests.get(img_url, headers=HEADERS)
    img_original = Image.open(io.BytesIO(img_res.content)).convert("RGBA")
    larg_o, alt_o = img_original.size
    prop_o = larg_o / alt_o

    if tipo_arte == "FEED":
        TAMANHO = 1000
        # Reutiliza sua lógica de redimensionamento do Feed
        if prop_o > 1.0:
            n_alt = TAMANHO
            n_larg = int(n_alt * prop_o)
            img_redim = img_original.resize((n_larg, n_alt), Image.LANCZOS)
            margem = (n_larg - TAMANHO) // 2
            canvas = img_redim.crop((margem, 0, margem + TAMANHO, TAMANHO))
        else:
            n_larg = TAMANHO
            n_alt = int(n_larg / prop_o)
            img_redim = img_original.resize((n_larg, n_alt), Image.LANCZOS)
            margem = (n_alt - TAMANHO) // 2
            canvas = img_redim.crop((0, margem, TAMANHO, margem + TAMANHO))

        if os.path.exists(TEMPLATE_FEED):
            tmp = Image.open(TEMPLATE_FEED).convert("RGBA").resize((TAMANHO, TAMANHO))
            canvas.alpha_composite(tmp)
        
        draw = ImageDraw.Draw(canvas)
        # Lógica do texto do Feed adaptada
        tam_f = 85
        while tam_f > 20:
            fonte = ImageFont.truetype(CAMINHO_FONTE, tam_f)
            linhas = textwrap.wrap(titulo, width=20) # Simplificado para o exemplo
            if len(linhas) <= 3: break
            tam_f -= 2
        
        y_f = 811 - (len(linhas) * tam_f // 2)
        for lin in linhas:
            draw.text((488, y_f), lin, fill="black", font=fonte, anchor="mm")
            y_f += tam_f + 4
            
    else: # STORY
        # Reutiliza sua lógica de Story
        LARG_S, ALT_S = 940, 541
        img_s_redim = img_original.resize((LARG_S, ALT_S), Image.LANCZOS)
        canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 255))
        canvas.paste(img_s_redim, (69, 504))
        
        if os.path.exists(TEMPLATE_STORIE):
            tmp = Image.open(TEMPLATE_STORIE).convert("RGBA").resize((1080, 1920))
            canvas.alpha_composite(tmp)
            
        draw = ImageDraw.Draw(canvas)
        fonte = ImageFont.truetype(CAMINHO_FONTE, 60)
        draw.text((69, 1079), titulo[:100], fill="white", font=fonte)

    return canvas.convert("RGB")

# --- INTERFACE ---
st.title("🚀 Gerador Destaque Toledo")

url_input = st.text_input("Cole o link da matéria:")

if url_input:
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Gerar Feed (Quadrado)"):
            img = processar_imagem_web(url_input, "FEED")
            st.image(img, caption="Prévia Feed")
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            st.download_button("Baixar Post", buf.getvalue(), "post.jpg", "image/jpeg")

    with col2:
        if st.button("Gerar Story (Vertical)"):
            img = processar_imagem_web(url_input, "STORY")
            st.image(img, caption="Prévia Story", width=250)
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            st.download_button("Baixar Story", buf.getvalue(), "story.jpg", "image/jpeg")