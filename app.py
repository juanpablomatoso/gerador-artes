import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os
import sqlite3
from datetime import datetime

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Painel Destaque Toledo", layout="wide", page_icon="📸")

# --- 2. BANCO DE DADOS (Expansão para Pautas e Links) ---
def init_db():
    conn = sqlite3.connect('agenda_destaque.db')
    c = conn.cursor()
    # Tabela Agenda (Mantida)
    c.execute('''CREATE TABLE IF NOT EXISTS agenda (dia TEXT PRIMARY KEY, pauta TEXT)''')
    # Tabela de Pautas para o Brayan
    c.execute('''CREATE TABLE IF NOT EXISTS pautas_trabalho 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, link_ref TEXT, 
                  status TEXT, checklist_feed INTEGER, checklist_story INTEGER)''')
    # Tabela de Links Rápidos
    c.execute('''CREATE TABLE IF NOT EXISTS links_rapidos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, url TEXT)''')
    conn.commit()
    conn.close()

# Funções de Banco para a Agenda (Mantidas)
def salvar_pauta(dia, pauta):
    conn = sqlite3.connect('agenda_destaque.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO agenda (dia, pauta) VALUES (?, ?)", (dia, pauta))
    conn.commit() ; conn.close()

def carregar_pautas():
    conn = sqlite3.connect('agenda_destaque.db')
    c = conn.cursor()
    c.execute("SELECT * FROM agenda")
    dados = dict(c.fetchall())
    conn.close() ; return dados

# Novas Funções de Gestão (Adicionais)
def adicionar_pauta_db(titulo, link):
    conn = sqlite3.connect('agenda_destaque.db')
    c = conn.cursor()
    c.execute("INSERT INTO pautas_trabalho (titulo, link_ref, status, checklist_feed, checklist_story) VALUES (?, ?, '🔴 Pendente', 0, 0)", (titulo, link))
    conn.commit() ; conn.close()

def atualizar_status_pauta(id_pauta, novo_status):
    conn = sqlite3.connect('agenda_destaque.db')
    c = conn.cursor()
    c.execute("UPDATE pautas_trabalho SET status = ? WHERE id = ?", (novo_status, id_pauta))
    conn.commit() ; conn.close()

init_db()
pautas_salvas = carregar_pautas()

# --- 3. ESTILIZAÇÃO CSS (Inalterada) ---
st.markdown("""
    <style>
    .main { background-color: #f4f7f9; }
    .topo-titulo {
        text-align: center; padding: 30px;
        background: linear-gradient(90deg, #004a99 0%, #007bff 100%);
        color: white; border-radius: 0 0 20px 20px;
        margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .topo-titulo h1 { margin: 0; font-size: 2.5rem; font-weight: 800; }
    .card-pauta { background: white; padding: 15px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. FUNÇÕES CORE (Geração de Artes - NÃO MEXIDAS) ---
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
                if len(titulo_limpo) > 15: noticias.append({"titulo": titulo_limpo, "url": href})
        return noticias[:12]
    except: return []

def processar_artes_web(url, tipo_saida):
    # Lógica de imagem idêntica à original para garantir que nada mude no resultado final
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
                n_alt = TAM ; n_larg = int(TAM * prop_o)
                img_f = img_original.resize((n_larg, n_alt), Image.LANCZOS).crop(((n_larg-TAM)//2, 0, (n_larg-TAM)//2+TAM, TAM))
            else:
                n_larg = TAM ; n_alt = int(TAM / prop_o)
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
            return img_f.convert("RGB")
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
            return canvas.convert("RGB")
    except: return None

# --- 5. INTERFACE ---
st.markdown(f'<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1><p>Operação: Juan Matoso & Brayan Welter</p></div>', unsafe_allow_html=True)

aba_gerador, aba_fluxo, aba_agenda, aba_links = st.tabs([
    "🎨 GERADOR DE ARTES", "📝 FLUXO BRAYAN", "📅 AGENDA SEMANAL", "🔗 LINKS ÚTEIS"
])

# ABA 1: GERADOR (MANTIDA)
with aba_gerador:
    col_lista, col_trabalho = st.columns([1, 1.8])
    with col_lista:
        st.markdown("### 📰 Notícias Recentes")
        if st.button("🔄 Sincronizar"): st.rerun()
        lista = obter_lista_noticias()
        for item in lista:
            if st.button(item['titulo'], key=f"gen_{item['url']}"):
                st.session_state.url_ativa = item['url']
    with col_trabalho:
        url_ativa = st.text_input("📍 Link da Notícia:", value=st.session_state.get('url_ativa', ''))
        if url_ativa:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🖼️ GERAR FEED"):
                    img = processar_artes_web(url_ativa, "FEED")
                    if img: 
                        st.image(img, use_container_width=True)
                        buf = io.BytesIO(); img.save(buf, format="JPEG", quality=95)
                        st.download_button("📥 Baixar Feed", buf.getvalue(), "feed.jpg", "image/jpeg")
            with c2:
                if st.button("📱 GERAR STORY"):
                    img = processar_artes_web(url_ativa, "STORY")
                    if img: 
                        st.image(img, width=280)
                        buf = io.BytesIO(); img.save(buf, format="JPEG", quality=95)
                        st.download_button("📥 Baixar Story", buf.getvalue(), "story.jpg", "image/jpeg")

# ABA 2: NOVO FLUXO DE TRABALHO (Para o Brayan)
with aba_fluxo:
    st.markdown("### 📝 Enviar Matéria para o Brayan Welter")
    with st.expander("➕ Lançar Nova Matéria"):
        t_pauta = st.text_input("Título da Matéria:")
        l_pauta = st.text_input("Link de Referência (opcional):")
        if st.button("Enviar para Fila"):
            if t_pauta:
                adicionar_pauta_db(t_pauta, l_pauta)
                st.success("Enviado com sucesso!")
                st.rerun()

    st.markdown("---")
    st.markdown("### 📋 Fila de Publicação")
    conn = sqlite3.connect('agenda_destaque.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pautas_trabalho WHERE status != '✅ Concluído' ORDER BY id DESC")
    pautas = cursor.fetchall()
    conn.close()

    for p in pautas:
        with st.container():
            st.markdown(f"""<div class='card-pauta'>
                <b>📌 {p[1]}</b><br><small>Ref: {p[2]}</small>
            </div>""", unsafe_allow_html=True)
            col_b1, col_b2, col_b3 = st.columns([1,1,1])
            with col_b1:
                if st.button(f"Marcar Publicado", key=f"pub_{p[0]}"):
                    atualizar_status_pauta(p[0], "✅ Concluído")
                    st.rerun()
            with col_b2:
                st.checkbox("Feed OK", key=f"feed_check_{p[0]}")
            with col_b3:
                st.checkbox("Story OK", key=f"story_check_{p[0]}")

# ABA 3: AGENDA (MANTIDA)
with aba_agenda:
    st.markdown("### 📅 Planejamento Semanal (Auto-salvamento)")
    dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    cols = st.columns(7)
    for i, dia in enumerate(dias):
        with cols[i]:
            st.markdown(f"**{dia}**")
            valor_ini = pautas_salvas.get(dia, "")
            texto = st.text_area("Pauta:", value=valor_ini, key=f"txt_{dia}", height=350, label_visibility="collapsed")
            if texto != valor_ini:
                salvar_pauta(dia, texto)
                st.toast(f"Salvo: {dia}", icon="✅")

# ABA 4: LINKS ÚTEIS
with aba_links:
    st.markdown("### 🔗 Mural de Acesso Rápido")
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        st.info("🌐 **SITES ÚTEIS**")
        st.write("- [Painel Blogger](https://www.blogger.com)")
        st.write("- [Gerenciador de Anúncios Meta](https://adsmanager.facebook.com)")
    with col_l2:
        st.info("📂 **RECURSOS**")
        st.write("- [Banco de Imagens Pixabay](https://pixabay.com)")
        st.write("- [TinyPNG (Otimizar Fotos)](https://tinypng.com)")
