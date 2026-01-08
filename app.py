import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os

# Configuração da página - Tema escuro/claro automático do Streamlit
st.set_page_config(page_title="Central Destaque Toledo", page_icon="🚀", layout="wide")

# Estilização Personalizada (CSS)
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; }
    .main { background-color: #f5f7f9; }
    .sidebar .sidebar-content { background-image: linear-gradient(#2e7bcf,#2e7bcf); color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURAÇÕES ---
CAMINHO_FONTE = "Shoika Bold.ttf"
TEMPLATE_FEED = "template_feed.png"
TEMPLATE_STORIE = "template_storie.png"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# --- FUNÇÃO DE SCRAPING MELHORADA ---
@st.cache_data(ttl=600) # Guarda a lista por 10 min para ficar instantâneo
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
                if len(titulo_limpo) > 20:
                    noticias.append({"titulo": titulo_limpo, "url": href})
        return noticias[:12]
    except:
        return []

def processar_artes_web(url, tipo_saida):
    # (Mantive sua lógica exata de processamento de imagem aqui)
    # [A lógica do seu post anterior entra aqui sem alterações nos cálculos]
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
                if alt_bloco_f <= 165 and len(linhas_f) <= 3: break
                tam_f -= 1
            
            y_f = 811 - (alt_bloco_f // 2)
            for lin in linhas_f:
                larg_l = draw_f.textbbox((0, 0), lin, font=fonte_f)[2]
                draw_f.text((488 - (larg_l // 2), y_f), lin, fill="black", font=fonte_f)
                y_f += tam_f + 4
            return fundo_f.convert("RGB"), titulo

        else: # STORY
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
                if alt_bloco_s <= 300 and len(linhas_s) <= 4: break
                tam_s -= 2
                
            y_s = 1079
            for lin in linhas_s:
                draw_s.text((69, y_s), lin, fill="white", font=fonte_s)
                y_s += tam_s + 12
            return storie_canvas.convert("RGB"), titulo
    except Exception as e:
        st.error(f"Erro: {e}")
        return None, None

# --- ESTRUTURA DA PÁGINA ---

# Barra Lateral (Sidebar) para as notícias
with st.sidebar:
    st.image("https://www.destaquetoledo.com.br/images/logo.png", width=200) # Logo do site
    st.title("📰 Últimas Notícias")
    if st.button("🔄 Sincronizar Agora"):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    lista = obter_lista_noticias()
    for item in lista:
        if st.button(item['titulo'], key=item['url']):
            st.session_state.url_ativa = item['url']

# Área Principal
st.header("🎨 Central de Criação Destaque")

if 'url_ativa' not in st.session_state:
    st.info("👈 Selecione uma notícia na barra lateral para começar!")
else:
    url_final = st.session_state.url_ativa
    st.caption(f"📍 Link ativo: {url_final}")
    
    col_f, col_s = st.columns(2)
    
    with col_f:
        st.subheader("🖼️ Post para Feed")
        if st.button("Gerar Versão Quadrada"):
            with st.spinner("Desenhando arte..."):
                img, tit = processar_artes_web(url_final, "FEED")
                if img:
                    st.image(img, use_container_width=True)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=95)
                    st.download_button(f"📥 Baixar Post Feed", buf.getvalue(), f"feed_{tit[:20]}.jpg", "image/jpeg")

    with col_s:
        st.subheader("📱 Post para Stories")
        if st.button("Gerar Versão Story"):
            with st.spinner("Desenhando arte..."):
                img, tit = processar_artes_web(url_final, "STORY")
                if img:
                    # No Story, mostramos um pouco menor na prévia para não ocupar a tela toda
                    st.image(img, width=320)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=95)
                    st.download_button(f"📥 Baixar Story", buf.getvalue(), f"story_{tit[:20]}.jpg", "image/jpeg")
