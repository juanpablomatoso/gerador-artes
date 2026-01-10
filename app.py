import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os
import sqlite3
from datetime import datetime

# --- 1. CONFIGURAÇÃO E ESTILO ---
st.set_page_config(page_title="Painel Destaque Toledo", layout="wide", page_icon="📸")

st.markdown("""
    <style>
    .main { background-color: #f4f7f9; }
    .topo-titulo {
        text-align: center; padding: 25px;
        background: linear-gradient(90deg, #004a99 0%, #007bff 100%);
        color: white; border-radius: 15px; margin-bottom: 25px;
    }
    /* Cores de Prioridade */
    .prioridade-urgente { background-color: #f8d7da; color: #721c24; padding: 10px; border-radius: 8px; border-left: 8px solid #dc3545; font-weight: bold; margin-bottom: 10px; }
    .prioridade-normal { background-color: #e2e3e5; color: #383d41; padding: 10px; border-radius: 8px; border-left: 8px solid #6c757d; font-weight: bold; margin-bottom: 10px; }
    .prioridade-programar { background-color: #cce5ff; color: #004085; padding: 10px; border-radius: 8px; border-left: 8px solid #007bff; font-weight: bold; margin-bottom: 10px; }
    .status-concluido { background-color: #d4edda; color: #155724; padding: 10px; border-radius: 8px; border-left: 8px solid #28a745; opacity: 0.8; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('agenda_destaque.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS agenda (dia TEXT PRIMARY KEY, pauta TEXT)')
    # Adicionada coluna 'prioridade'
    c.execute('''CREATE TABLE IF NOT EXISTS pautas_trabalho 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, link_ref TEXT, status TEXT, data_envio TEXT, prioridade TEXT)''')
    conn.commit(); conn.close()

def salvar_pauta_agenda(dia, pauta):
    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO agenda (dia, pauta) VALUES (?, ?)", (dia, pauta))
    conn.commit(); conn.close()

def excluir_pauta(id_pauta):
    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
    c.execute("DELETE FROM pautas_trabalho WHERE id = ?", (id_pauta,))
    conn.commit(); conn.close()

init_db()

# --- 3. LOGIN (Juan Matoso e Brayan Welter) ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown('<div class="topo-titulo"><h1>Acesso Restrito</h1><p>Juan Matoso & Brayan Welter</p></div>', unsafe_allow_html=True)
    _, col2, _ = st.columns([1,1,1])
    with col2:
        u = st.text_input("Usuário").lower()
        s = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if u == "juan" and s == "juan123":
                st.session_state.autenticado = True; st.session_state.perfil = "juan"; st.rerun()
            elif u == "brayan" and s == "brayan123":
                st.session_state.autenticado = True; st.session_state.perfil = "brayan"; st.rerun()
            else: st.error("Incorreto")
else:
    # --- 4. FUNÇÕES DE ARTE (RESTURADAS E INTOCÁVEIS) ---
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
                    n_alt = TAM; n_larg = int(TAM * prop_o)
                    img_f = img_original.resize((n_larg, n_alt), Image.LANCZOS).crop(((n_larg-TAM)//2, 0, (n_larg-TAM)//2+TAM, TAM))
                else:
                    n_larg = TAM; n_alt = int(TAM / prop_o)
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
    st.markdown(f'<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1><p>Logado como: {st.session_state.perfil.capitalize()}</p></div>', unsafe_allow_html=True)
    
    if st.session_state.perfil == "juan":
        aba_gerador, aba_fluxo, aba_agenda = st.tabs(["🎨 GERADOR DE ARTES", "📝 FLUXO BRAYAN", "📅 AGENDA"])
        
        with aba_gerador:
            col_lista, col_trabalho = st.columns([1, 1.8])
            with col_lista:
                st.subheader("📰 Notícias")
                if st.button("🔄 Sincronizar"): st.rerun()
                lista = obter_lista_noticias()
                for item in lista:
                    if st.button(item['titulo'], key=f"btn_{item['url']}", help="Clique para carregar esta notícia"):
                        st.session_state.url_ativa = item['url']
            with col_trabalho:
                url_ativa = st.text_input("📍 Link da matéria para gerar arte:", value=st.session_state.get('url_ativa', ''))
                if url_ativa:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🖼️ GERAR FEED", help="Cria arte quadrada para o Feed do Instagram"):
                            img = processar_artes_web(url_ativa, "FEED")
                            if img:
                                st.image(img, use_container_width=True)
                                buf = io.BytesIO(); img.save(buf, format="JPEG"); st.download_button("📥 Baixar Feed", buf.getvalue(), "feed.jpg")
                    with c2:
                        if st.button("📱 GERAR STORY", help="Cria arte vertical para os Stories"):
                            img = processar_artes_web(url_ativa, "STORY")
                            if img:
                                st.image(img, width=250)
                                buf = io.BytesIO(); img.save(buf, format="JPEG"); st.download_button("📥 Baixar Story", buf.getvalue(), "story.jpg")

        with aba_fluxo:
            col_add, col_ver = st.columns([1, 1.2])
            with col_add:
                st.subheader("🚀 Enviar Nova Matéria")
                with st.form("nova_pauta"):
                    t_m = st.text_input("Título")
                    l_m = st.text_input("Link/Observação")
                    prio = st.select_slider("Prioridade", options=["Programar", "Normal", "URGENTE"])
                    if st.form_submit_button("Enviar para o Brayan"):
                        conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
                        c.execute("INSERT INTO pautas_trabalho (titulo, link_ref, status, data_envio, prioridade) VALUES (?, ?, 'Pendente', ?, ?)", 
                                 (t_m, l_m, datetime.now().strftime("%H:%M"), prio))
                        conn.commit(); conn.close(); st.rerun()
            with col_ver:
                st.subheader("📋 Matérias em Andamento")
                conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
                c.execute("SELECT * FROM pautas_trabalho WHERE status != '✅ Concluído' ORDER BY id DESC"); pautas = c.fetchall(); conn.close()
                for p in pautas:
                    cor_classe = "prioridade-urgente" if p[5] == "URGENTE" else ("prioridade-programar" if p[5] == "Programar" else "prioridade-normal")
                    st.markdown(f"<div class='{cor_classe}'>{p[5]} | {p[4]}<br>{p[1]}</div>", unsafe_allow_html=True)
                    c_ed1, c_ed2 = st.columns(2)
                    with c_ed1:
                        if st.button("🗑️ Excluir", key=f"del_{p[0]}", help="Remove esta matéria da fila"):
                            excluir_pauta(p[0]); st.rerun()
                    with c_ed2:
                        st.write("Ref: " + p[2])

        with aba_agenda:
            # (Código da Agenda preservado como você disse estar tudo certo)
            dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
            cols = st.columns(7)
            conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
            c.execute("SELECT * FROM agenda"); p_db = dict(c.fetchall()); conn.close()
            for i, d in enumerate(dias):
                with cols[i]:
                    st.write(f"**{d}**")
                    v = p_db.get(d, "")
                    txt = st.text_area(d, value=v, key=f"ag_{d}", height=300, label_visibility="collapsed")
                    if txt != v: salvar_pauta_agenda(d, txt); st.toast(f"Salvo {d}")

    # --- VISÃO DO BRAYAN ---
    else:
        st.subheader("📋 Sua Fila de Trabalho")
        conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
        c.execute("SELECT * FROM pautas_trabalho WHERE status = 'Pendente' ORDER BY CASE WHEN prioridade='URGENTE' THEN 1 WHEN prioridade='Normal' THEN 2 ELSE 3 END"); p_br = c.fetchall(); conn.close()
        for pb in p_br:
            cor_pb = "prioridade-urgente" if pb[5] == "URGENTE" else ("prioridade-programar" if pb[5] == "Programar" else "prioridade-normal")
            st.markdown(f"<div class='{cor_pb}'>{pb[5].upper()} - Enviado às {pb[4]}<br><span style='font-size:1.3rem'>{pb[1]}</span><br><small>{pb[2]}</small></div>", unsafe_allow_html=True)
            if st.button("✅ CONCLUÍDO / JÁ POSTEI", key=f"br_fin_{pb[0]}", help="Clique aqui após publicar a matéria no site"):
                conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
                c.execute("UPDATE pautas_trabalho SET status = '✅ Concluído' WHERE id = ?", (pb[0],))
                conn.commit(); conn.close(); st.rerun()
