import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os

# Configuração da página
st.set_page_config(page_title="Painel Destaque - Editável", layout="wide", page_icon="🎨")

# --- ESTILIZAÇÃO CSS ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button {
        width: 100%;
        text-align: left !important;
        border-radius: 8px !important;
        border: 1px solid #e0e0e0 !important;
        background-color: white !important;
        padding: 12px !important;
        color: #333 !important;
    }
    .stButton>button:hover { border-color: #007bff !important; background-color: #f0f7ff !important; }
    
    /* Cores dos Botões de Geração */
    .btn-feed { background-color: #007bff !important; color: white !important; font-weight: bold !important; }
    .btn-story { background-color: #6f42c1 !important; color: white !important; font-weight: bold !important; }
    
    .logo-container { display: flex; justify-content: center; padding: 20px; background: white; border-radius: 0 0 20px 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURAÇÕES ---
CAMINHO_FONTE = "Shoika Bold.ttf"
TEMPLATE_FEED = "template_feed.png"
TEMPLATE_STORIE = "template_storie.png"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# --- FUNÇÕES ---
def obter_lista_noticias():
    try:
        url_site = "https://www.destaquetoledo.com.br/"
        res = requests.get(url_site, headers=HEADERS, timeout=10).text
        soup = BeautifulSoup(res, "html.parser")
        noticias = []
        for a in soup.find_all("a", href=True):
            href = a['href']
            if ".html" in href and "/20" in href and href not in [n['url'] for n in noticias]:
                t = a.get_text(strip=True)
                if len(t) > 15: noticias.append({"titulo": t, "url": href})
        return noticias[:12]
    except: return []

def processar_arte_custom(url, tipo, texto_custom, tam_fonte, ajuste_y):
    try:
        res_m = requests.get(url, headers=HEADERS).text
        soup_m = BeautifulSoup(res_m, "html.parser")
        
        # Se o usuário não editou, pega o original do site
        titulo_final = texto_custom if texto_custom else soup_m.find("h1").get_text(strip=True)
        
        corpo = soup_m.find(class_="post-body") or soup_m
        img_url = next(img.get("src") for img in corpo.find_all("img") if "logo" not in img.get("src").lower())
        
        img_res = requests.get(img_url, headers=HEADERS)
        img_o = Image.open(io.BytesIO(img_res.content)).convert("RGBA")
        larg_o, alt_o = img_o.size
        prop_o = larg_o / alt_o

        if tipo == "FEED":
            TAM = 1000
            if prop_o > 1.0:
                n_alt = TAM
                n_larg = int(TAM * prop_o)
                img_f = img_o.resize((n_larg, n_alt), Image.LANCZOS).crop(((n_larg-TAM)//2, 0, (n_larg-TAM)//2+TAM, TAM))
            else:
                n_larg = TAM
                n_alt = int(TAM / prop_o)
                img_f = img_o.resize((n_larg, n_alt), Image.LANCZOS).crop((0, (n_alt-TAM)//2, TAM, (n_alt-TAM)//2+TAM))
            
            if os.path.exists(TEMPLATE_FEED):
                img_f.alpha_composite(Image.open(TEMPLATE_FEED).convert("RGBA").resize((TAM, TAM)))
            
            draw = ImageDraw.Draw(img_f)
            fonte = ImageFont.truetype(CAMINHO_FONTE, tam_fonte)
            # Quebra de linha dinâmica baseada no tamanho da fonte escolhido
            linhas = textwrap.wrap(titulo_final, width=int(662/(fonte.getlength("W")*0.5/tam_fonte)))
            
            y_base = 811 + ajuste_y # 811 é o centro original
            alt_total = len(linhas) * tam_fonte
            y = y_base - (alt_total // 2)
            
            for l in linhas:
                w_l = draw.textbbox((0,0), l, font=fonte)[2]
                draw.text((488 - (w_l//2), y), l, fill="black", font=fonte)
                y += tam_fonte + 5
            return img_f.convert("RGB")

        else: # STORY
            L_S, A_S = 940, 541
            ratio = L_S / A_S
            ns_l, ns_a = (int(A_S*prop_o), A_S) if prop_o > ratio else (L_S, int(L_S/prop_o))
            img_s = img_o.resize((ns_l, ns_a), Image.LANCZOS).crop(((ns_l-L_S)//2, (ns_a-A_S)//2, (ns_l-L_S)//2+L_S, (ns_a-A_S)//2+A_S))
            
            canvas = Image.new("RGBA", (1080, 1920), (0,0,0,0))
            canvas.paste(img_s, (69, 504))
            if os.path.exists(TEMPLATE_STORIE):
                canvas.alpha_composite(Image.open(TEMPLATE_STORIE).convert("RGBA").resize((1080, 1920)))
            
            draw = ImageDraw.Draw(canvas)
            fonte = ImageFont.truetype(CAMINHO_FONTE, tam_fonte)
            linhas = textwrap.wrap(titulo_final, width=int(912/(fonte.getlength("W")*0.5/tam_fonte)))
            
            y = 1079 + ajuste_y
            for l in lns:
                draw.text((69, y), l, fill="white", font=fonte)
                y += tam_fonte + 10
            return canvas.convert("RGB")
    except: return None

# --- UI ---
st.markdown('<div class="logo-container"><img src="https://www.destaquetoledo.com.br/images/logo.png" width="250"></div>', unsafe_allow_html=True)

col_lista, col_editor = st.columns([1, 1.8])

with col_lista:
    st.subheader("📰 Notícias")
    if st.button("🔄 Atualizar"): st.rerun()
    lista = obter_lista_noticias()
    for item in lista:
        if st.button(item['titulo'], key=item['url']):
            st.session_state.url_ativa = item['url']
            st.session_state.txt_edit = item['titulo'] # Carrega o título para o editor

with col_editor:
    if 'url_ativa' in st.session_state:
        st.subheader("⚙️ Personalizar Arte")
        
        # Área de Edição
        txt_editado = st.text_area("Editar Título:", value=st.session_state.get('txt_edit', ''), height=100)
        
        c_p1, c_p2 = st.columns(2)
        tam_f = c_p1.slider("Tamanho da Fonte:", 30, 120, 75)
        pos_y = c_p2.slider("Ajuste de Altura (Sobe/Desce):", -100, 100, 0)
        
        st.divider()
        
        c1, c2 = st.columns(2)
        if c1.button("🖼️ GERAR FEED", use_container_width=True):
            res = processar_arte_custom(st.session_state.url_ativa, "FEED", txt_editado, tam_f, pos_y)
            if res:
                st.image(res)
                buf = io.BytesIO()
                res.save(buf, format="JPEG")
                st.download_button("📥 Baixar Feed", buf.getvalue(), "feed.jpg")

        if c2.button("📱 GERAR STORY", use_container_width=True):
            res = processar_arte_custom(st.session_state.url_ativa, "STORY", txt_editado, tam_f, pos_y)
            if res:
                st.image(res, width=300)
                buf = io.BytesIO()
                res.save(buf, format="JPEG")
                st.download_button("📥 Baixar Story", buf.getvalue(), "story.jpg")
    else:
        st.info("👈 Selecione uma notícia para liberar o editor.")
