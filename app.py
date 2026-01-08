import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os

# Configuração da página
st.set_page_config(page_title="Central Destaque Toledo", page_icon="📸", layout="wide")

# CSS para forçar um visual limpo e alinhar as miniaturas
st.markdown("""
    <style>
    [data-testid="stSidebar"] { min-width: 450px; max-width: 450px; }
    .stButton > button {
        text-align: left !important;
        height: auto !important;
        padding: 10px !important;
        border-radius: 8px !important;
    }
    /* Ajuste para as imagens na barra lateral não ficarem gigantes */
    [data-testid="stSidebar"] img {
        border-radius: 5px;
        object-fit: cover;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONFIGURAÇÕES ---
CAMINHO_FONTE = "Shoika Bold.ttf"
TEMPLATE_FEED = "template_feed.png"
TEMPLATE_STORIE = "template_storie.png"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
URL_SITE = "https://www.destaquetoledo.com.br/"

# --- FUNÇÃO DE BUSCA DE NOTÍCIAS (VERSÃO ULTRA COMPATÍVEL) ---
@st.cache_data(ttl=300)
def obter_lista_noticias_v3():
    try:
        res = requests.get(URL_SITE, headers=HEADERS, timeout=15).text
        soup = BeautifulSoup(res, "html.parser")
        noticias = []
        
        # O site organiza as notícias em blocos. Vamos pegar todos os links que pareçam notícias
        tags_a = soup.find_all("a", href=True)
        
        for a in tags_a:
            href = a['href']
            # Filtro para garantir que é uma notícia de 2024/2025/2026
            if ".html" in href and ("/202" in href):
                url_completa = href if href.startswith('http') else f"https://www.destaquetoledo.com.br{href}"
                
                # Evitar duplicados
                if url_completa in [n['url'] for n in noticias]: continue
                
                # Tenta achar o título
                titulo = a.get_text(strip=True)
                if len(titulo) < 20: 
                    # Se o texto do link for curto, tenta buscar num H2 ou H3 próximo
                    parent = a.find_parent(['div', 'article', 'li'])
                    if parent:
                        h_tag = parent.find(['h1', 'h2', 'h3', 'h4'])
                        if h_tag: titulo = h_tag.get_text(strip=True)

                # --- LÓGICA DE IMAGEM MELHORADA ---
                img_url = None
                # Busca imagem dentro do link ou no "vizinho" mais próximo (parent)
                contexto = a.find_parent(['div', 'article', 'li']) or a
                img_tag = contexto.find("img")
                
                if img_tag:
                    # Tenta todos os atributos onde o link da imagem pode estar escondido
                    img_url = (
                        img_tag.get("data-src") or 
                        img_tag.get("data-lazy-src") or 
                        img_tag.get("data-original") or 
                        img_tag.get("src")
                    )
                
                if img_url and titulo and len(titulo) > 15:
                    # Limpa a URL da imagem
                    if img_url.startswith('//'): img_url = "https:" + img_url
                    elif img_url.startswith('/'): img_url = f"https://www.destaquetoledo.com.br{img_url}"
                    
                    noticias.append({
                        "titulo": titulo,
                        "url": url_completa,
                        "img": img_url
                    })
        
        return noticias[:12]
    except Exception as e:
        st.error(f"Erro ao ler site: {e}")
        return []

# --- LÓGICA DE PROCESSAMENTO DE IMAGEM (MANTIDA A SUA) ---
def processar_artes(url, tipo):
    try:
        res_m = requests.get(url, headers=HEADERS).text
        soup_m = BeautifulSoup(res_m, "html.parser")
        titulo = soup_m.find("h1").get_text(strip=True)
        corpo = soup_m.find(class_="post-body") or soup_m
        
        # Pega a imagem principal da matéria
        img_url = next(img.get("src") for img in corpo.find_all("img") if "logo" not in img.get("src").lower())
        if not img_url.startswith('http'): img_url = f"https://www.destaquetoledo.com.br{img_url}"
        
        img_res = requests.get(img_url, headers=HEADERS)
        img_original = Image.open(io.BytesIO(img_res.content)).convert("RGBA")
        larg_o, alt_o = img_original.size
        prop_o = larg_o / alt_o

        if tipo == "FEED":
            TAMANHO = 1000
            if prop_o > 1.0:
                n_alt = TAMANHO
                n_larg = int(n_alt * prop_o)
                img_redim = img_original.resize((n_larg, n_alt), Image.LANCZOS)
                margem = (n_larg - TAMANHO) // 2
                fundo = img_redim.crop((margem, 0, margem + TAMANHO, TAMANHO))
            else:
                n_larg = TAMANHO
                n_alt = int(n_larg / prop_o)
                img_redim = img_original.resize((n_larg, n_alt), Image.LANCZOS)
                margem = (n_alt - TAMANHO) // 2
                fundo = img_redim.crop((0, margem, TAMANHO, margem + TAMANHO))

            if os.path.exists(TEMPLATE_FEED):
                tmp = Image.open(TEMPLATE_FEED).convert("RGBA").resize((TAMANHO, TAMANHO))
                fundo.alpha_composite(tmp)

            draw = ImageDraw.Draw(fundo)
            tam = 85
            while tam > 20:
                fonte = ImageFont.truetype(CAMINHO_FONTE, tam)
                limite = int(662 / (fonte.getlength("W") * 0.55))
                linhas = textwrap.wrap(titulo, width=max(10, limite))
                alt_bloco = (len(linhas) * tam) + ((len(linhas)-1) * 4)
                if alt_bloco <= 165 and len(linhas) <= 3: break
                tam -= 1
            
            y = 811 - (alt_bloco // 2)
            for lin in linhas:
                larg_l = draw.textbbox((0, 0), lin, font=fonte)[2]
                draw.text((488 - (larg_l // 2), y), lin, fill="black", font=fonte)
                y += tam + 4
            return fundo.convert("RGB"), titulo

        else: # STORY
            LARG_S, ALT_S = 940, 541
            ratio_a = LARG_S / ALT_S
            ns_larg, ns_alt = (int(ALT_S * prop_o), ALT_S) if prop_o > ratio_a else (LARG_S, int(LARG_S / prop_o))
            img_redim = img_original.resize((ns_larg, ns_alt), Image.LANCZOS)
            l_cut, t_cut = (ns_larg - LARG_S) / 2, (ns_alt - ALT_S) / 2
            img_final = img_redim.crop((l_cut, t_cut, l_cut + LARG_S, t_cut + ALT_S))

            canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            canvas.paste(img_final, (69, 504))
            if os.path.exists(TEMPLATE_STORIE):
                tmp = Image.open(TEMPLATE_STORIE).convert("RGBA").resize((1080, 1920))
                canvas.alpha_composite(tmp)

            draw = ImageDraw.Draw(canvas)
            tam = 60
            while tam > 20:
                fonte = ImageFont.truetype(CAMINHO_FONTE, tam)
                limite = int(912 / (fonte.getlength("W") * 0.55))
                linhas = textwrap.wrap(titulo, width=max(10, limite))
                alt_bloco = (len(linhas) * tam) + (len(linhas) * 10)
                if alt_bloco <= 300 and len(linhas) <= 4: break
                tam -= 2
            y = 1079
            for lin in linhas:
                draw.text((69, y), lin, fill="white", font=fonte)
                y += tam + 12
            return canvas.convert("RGB"), titulo

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
        return None, None

# --- INTERFACE ---
with st.sidebar:
    st.image("https://www.destaquetoledo.com.br/images/logo.png", width=200)
    if st.button("🔄 Sincronizar Portal"):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    lista_noticias = obter_lista_noticias_v3()
    
    if not lista_noticias:
        st.warning("Nenhuma notícia encontrada. Tente atualizar.")
    
    for item in lista_noticias:
        col_capa, col_btn = st.columns([0.35, 0.65])
        
        # Mostra a imagem na lateral
        if item['img']:
            col_capa.image(item['img'], use_container_width=True)
        else:
            col_capa.write("🖼️")
            
        if col_btn.button(item['titulo'], key=item['url']):
            st.session_state.url_ativa = item['url']
        st.divider()

st.title("🎨 Central de Criação Destaque")

if 'url_ativa' not in st.session_state:
    st.info("👈 Selecione uma notícia na barra lateral para carregar as artes.")
else:
    url_ativa = st.session_state.url_ativa
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("🖼️ Post para Feed")
        if st.button("Gerar Quadrado"):
            with st.spinner("Criando..."):
                img, tit = processar_artes(url_ativa, "FEED")
                if img:
                    st.image(img, use_container_width=True)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=95)
                    st.download_button("📥 Baixar Feed", buf.getvalue(), f"feed_{tit[:10]}.jpg", "image/jpeg")

    with c2:
        st.subheader("📱 Post para Stories")
        if st.button("Gerar Story"):
            with st.spinner("Criando..."):
                img, tit = processar_artes(url_ativa, "STORY")
                if img:
                    st.image(img, width=300)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=95)
                    st.download_button("📥 Baixar Story", buf.getvalue(), f"story_{tit[:10]}.jpg", "image/jpeg")
