import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os

# Configuração da página
st.set_page_config(page_title="Central Destaque Toledo", page_icon="🚀", layout="wide")

# CSS para estabilizar o visual e as fontes
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 400px; max-width: 450px; }
    .stButton > button { width: 100%; text-align: left !important; height: auto !important; padding: 10px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURAÇÕES BASE ---
# Usando os caminhos que você já configurou no seu computador
URL_SITE = "https://www.destaquetoledo.com.br/"
CAMINHO_FONTE = r"C:\Users\juanm\OneDrive\Área de Trabalho\Artes Insta\Shoika Bold.ttf"
TEMPLATE_FEED = r"C:\Users\juanm\OneDrive\Área de Trabalho\Artes Insta\template_feed.png"
TEMPLATE_STORIE = r"C:\Users\juanm\OneDrive\Área de Trabalho\Artes Insta\template_storie.png"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

# --- FUNÇÕES DE BUSCA ---
@st.cache_data(ttl=60) # Atualiza automaticamente a cada 1 minuto
def buscar_noticias_portal():
    try:
        res = requests.get(URL_SITE, headers=HEADERS, timeout=15).text
        soup = BeautifulSoup(res, "html.parser")
        dados = []
        
        # Procura por todos os blocos de notícias possíveis
        for item in soup.find_all(['div', 'article'], class_=['post-item', 'post-column', 'item']):
            link_tag = item.find("a", href=True)
            if not link_tag or ".html" not in link_tag['href']: continue
            
            url = link_tag['href']
            if not url.startswith('http'): url = URL_SITE + url.lstrip('/')
            
            # Título
            titulo = link_tag.get_text(strip=True)
            if len(titulo) < 10:
                h = item.find(['h2', 'h3'])
                if h: titulo = h.get_text(strip=True)
            
            # Imagem (Tenta vários atributos comuns)
            img_tag = item.find("img")
            img_url = None
            if img_tag:
                img_url = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")
                if img_url and not img_url.startswith('http'): img_url = URL_SITE + img_url.lstrip('/')

            if url not in [d['url'] for d in dados] and titulo:
                dados.append({"titulo": titulo, "url": url, "img": img_url})
        
        return dados[:12]
    except:
        return []

def gerar_arte(url, tipo):
    try:
        res_m = requests.get(url, headers=HEADERS, timeout=15).text
        soup_m = BeautifulSoup(res_m, "html.parser")
        
        titulo = soup_m.find("h1").get_text(strip=True)
        corpo = soup_m.find(class_="post-body") or soup_m
        # Pega a primeira imagem que não seja logo
        img_url = next(img.get("src") for img in corpo.find_all("img") if "logo" not in img.get("src").lower())
        if not img_url.startswith('http'): img_url = URL_SITE + img_url.lstrip('/')
        
        img_res = requests.get(img_url, headers=HEADERS)
        img_raw = Image.open(io.BytesIO(img_res.content)).convert("RGBA")
        larg, alt = img_raw.size
        prop = larg / alt

        if tipo == "FEED":
            # Lógica de redimensionamento do Feed
            TAM = 1000
            if prop > 1.0:
                n_alt = TAM
                n_larg = int(TAM * prop)
                img_redim = img_raw.resize((n_larg, n_alt), Image.LANCZOS)
                img_final = img_redim.crop(((n_larg - TAM)//2, 0, (n_larg - TAM)//2 + TAM, TAM))
            else:
                n_larg = TAM
                n_alt = int(TAM / prop)
                img_redim = img_raw.resize((n_larg, n_alt), Image.LANCZOS)
                img_final = img_redim.crop((0, (n_alt - TAM)//2, TAM, (n_alt - TAM)//2 + TAM))
            
            if os.path.exists(TEMPLATE_FEED):
                tmp = Image.open(TEMPLATE_FEED).convert("RGBA").resize((TAM, TAM))
                img_final.alpha_composite(tmp)
            
            draw = ImageDraw.Draw(img_final)
            tam_f = 85
            while tam_f > 20:
                fnt = ImageFont.truetype(CAMINHO_FONTE, tam_f)
                lns = textwrap.wrap(titulo, width=int(662/(fnt.getlength("W")*0.55)))
                if (len(lns)*tam_f) <= 165 and len(lns) <= 3: break
                tam_f -= 1
            
            y = 811 - ((len(lns)*tam_f)//2)
            for l in lns:
                draw.text((488 - (draw.textbbox((0,0), l, font=fnt)[2]//2), y), l, fill="black", font=fnt)
                y += tam_f + 4
            return img_final.convert("RGB"), titulo

        else: # STORY
            # Lógica de redimensionamento do Story
            L_S, A_S = 940, 541
            ratio = L_S / A_S
            ns_l, ns_a = (int(A_S * prop), A_S) if prop > ratio else (L_S, int(L_S / prop))
            img_redim = img_raw.resize((ns_l, ns_a), Image.LANCZOS)
            img_story = img_redim.crop(((ns_l - L_S)//2, (ns_a - A_S)//2, (ns_l - L_S)//2 + L_S, (ns_a - A_S)//2 + A_S))
            
            canvas = Image.new("RGBA", (1080, 1920), (0,0,0,0))
            canvas.paste(img_story, (69, 504))
            if os.path.exists(TEMPLATE_STORIE):
                tmp = Image.open(TEMPLATE_STORIE).convert("RGBA").resize((1080, 1920))
                canvas.alpha_composite(tmp)
            
            draw = ImageDraw.Draw(canvas)
            tam_s = 60
            while tam_s > 20:
                fnt = ImageFont.truetype(CAMINHO_FONTE, tam_s)
                lns = textwrap.wrap(titulo, width=int(912/(fnt.getlength("W")*0.55)))
                if (len(lns)*tam_s) <= 300 and len(lns) <= 4: break
                tam_s -= 2
            
            y = 1079
            for l in lns:
                draw.text((69, y), l, fill="white", font=fnt)
                y += tam_s + 12
            return canvas.convert("RGB"), titulo

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
        return None, None

# --- INTERFACE ---
with st.sidebar:
    st.title("🌐 Últimas Notícias")
    if st.button("🔄 Atualizar Tudo"):
        st.cache_data.clear()
        st.rerun()
    
    noticias = buscar_noticias_portal()
    if not noticias:
        st.error("Site fora do ar ou estrutura alterada.")
    
    for n in noticias:
        col_i, col_t = st.columns([0.3, 0.7])
        if n['img']: col_i.image(n['img'], use_container_width=True)
        else: col_i.write("🖼️")
        if col_t.button(n['titulo'][:60] + "...", key=n['url']):
            st.session_state.url_ativa = n['url']
        st.divider()

st.title("🎨 Central de Criação Destaque")

if 'url_ativa' not in st.session_state:
    st.info("👈 Selecione uma notícia ao lado para começar!")
else:
    u = st.session_state.url_ativa
    st.caption(f"📍 Matéria: {u}")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✨ Gerar Feed"):
            res, tit = gerar_arte(u, "FEED")
            if res:
                st.image(res)
                buf = io.BytesIO()
                res.save(buf, format="JPEG")
                st.download_button("📥 Baixar Feed", buf.getvalue(), f"feed_{tit[:20]}.jpg")

    with c2:
        if st.button("✨ Gerar Story"):
            res, tit = gerar_arte(u, "STORY")
            if res:
                st.image(res, width=300)
                buf = io.BytesIO()
                res.save(buf, format="JPEG")
                st.download_button("📥 Baixar Story", buf.getvalue(), f"story_{tit[:20]}.jpg")
