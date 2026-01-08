import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os

# Configuração da página
st.set_page_config(page_title="Gerador Destaque Toledo", layout="centered")

# --- CONFIGURAÇÕES DE CAMINHOS ---
CAMINHO_FONTE = "Shoika Bold.ttf"
TEMPLATE_FEED = "template_feed.png"
TEMPLATE_STORIE = "template_storie.png"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def processar_artes_web(url, tipo_saida):
    try:
        # 1. BUSCA DE DADOS
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
            # --- LÓGICA DO FEED (EXATAMENTE IGUAL AO SEU) ---
            TAMANHO_FEED = 1000
            if prop_o > 1.0:
                n_alt = TAMANHO_FEED
                n_larg = int(n_alt * prop_o)
                img_f_redim = img_original.resize((n_larg, n_alt), Image.LANCZOS)
                margem = (n_larg - TAMANHO_FEED) // 2
                fundo_f = img_f_redim.crop((margem, 0, margem + TAMANHO_FEED, TAMANHO_FEED))
            else:
                n_larg = TAMANHO_FEED
                n_alt = int(n_larg / prop_o)
                img_f_redim = img_original.resize((n_larg, n_alt), Image.LANCZOS)
                margem = (n_alt - TAMANHO_FEED) // 2
                fundo_f = img_f_redim.crop((0, margem, TAMANHO_FEED, margem + TAMANHO_FEED))

            if os.path.exists(TEMPLATE_FEED):
                tmp_f = Image.open(TEMPLATE_FEED).convert("RGBA").resize((TAMANHO_FEED, TAMANHO_FEED))
                fundo_f.alpha_composite(tmp_f)

            draw_f = ImageDraw.Draw(fundo_f)
            tam_f = 85
            while tam_f > 20:
                fonte_f = ImageFont.truetype(CAMINHO_FONTE, tam_f)
                limite_f = int(662 / (fonte_f.getlength("W") * 0.55))
                linhas_f = textwrap.wrap(titulo, width=max(10, limite_f))
                alt_bloco_f = (len(linhas_f) * tam_f) + ((len(linhas_f)-1) * 4)
                if alt_bloco_f <= 165 and len(linhas_f) <= 3: 
                    break
                tam_f -= 1
            
            y_f = 811 - (alt_bloco_f // 2)
            for lin in linhas_f:
                larg_l = draw_f.textbbox((0, 0), lin, font=fonte_f)[2]
                draw_f.text((488 - (larg_l // 2), y_f), lin, fill="black", font=fonte_f)
                y_f += tam_f + 4
            return fundo_f.convert("RGB")

        else:
            # --- LÓGICA DO STORY (EXATAMENTE IGUAL AO SEU) ---
            LARG_STORY, ALT_STORY = 940, 541
            ratio_a = LARG_STORY / ALT_STORY
            if prop_o > ratio_a:
                ns_alt = ALT_STORY
                ns_larg = int(ns_alt * prop_o)
            else:
                ns_larg = LARG_STORY
                ns_alt = int(ns_larg / prop_o)
            
            img_s_redim = img_original.resize((ns_larg, ns_alt), Image.LANCZOS)
            l_cut = (ns_larg - LARG_STORY) / 2
            t_cut = (ns_alt - ALT_STORY) / 2
            img_s_final = img_s_redim.crop((l_cut, t_cut, l_cut + LARG_STORY, t_cut + ALT_STORY))

            storie_canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            storie_canvas.paste(img_s_final, (69, 504))
            
            if os.path.exists(TEMPLATE_STORIE):
                tmp_s = Image.open(TEMPLATE_STORIE).convert("RGBA").resize((1080, 1920))
                storie_canvas.alpha_composite(tmp_s)

            draw_s = ImageDraw.Draw(storie_canvas)
            tam_s = 60
            while tam_s > 20:
                fonte_s = ImageFont.truetype(CAMINHO_FONTE, tam_s)
                limite_s = int(912 / (fonte_s.getlength("W") * 0.55))
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

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
        return None

# --- INTERFACE ---
st.title("🎨 Gerador Destaque Toledo")
st.write("Cole o link da matéria abaixo para gerar as artes com suas medidas originais.")

url_input = st.text_input("URL da Matéria:", placeholder="https://www.destaquetoledo.com.br/noticia/...")

if url_input:
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🖼️ Gerar Feed (1000x1000)"):
            with st.spinner("Processando Feed..."):
                img_f = processar_artes_web(url_input, "FEED")
                if img_f:
                    st.image(img_f, use_container_width=True)
                    buf = io.BytesIO()
                    img_f.save(buf, format="JPEG", quality=95)
                    st.download_button("📥 Baixar Feed", buf.getvalue(), "feed_destaque.jpg", "image/jpeg")

    with col2:
        if st.button("📱 Gerar Story (1080x1920)"):
            with st.spinner("Processando Story..."):
                img_s = processar_artes_web(url_input, "STORY")
                if img_s:
                    st.image(img_s, use_container_width=True)
                    buf = io.BytesIO()
                    img_s.save(buf, format="JPEG", quality=95)
                    st.download_button("📥 Baixar Story", buf.getvalue(), "story_destaque.jpg", "image/jpeg")
