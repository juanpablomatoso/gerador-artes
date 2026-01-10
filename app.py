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
st.set_page_config(page_title="Painel Destaque Toledo", layout="wide", page_icon="🎨")

# --- 2. ESTILIZAÇÃO CSS (PAINEL) ---
st.markdown("""
    <style>
    .main { background-color: #f4f7f9; }
    .topo-titulo {
        text-align: center; padding: 25px;
        background: linear-gradient(90deg, #004a99 0%, #007bff 100%);
        color: white; border-radius: 15px; margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .card-urgente { background-color: #ffdce0; color: #a51d2d; padding: 15px; border-radius: 12px; border-left: 10px solid #dc3545; margin-bottom: 15px; }
    .card-normal { background-color: #fff3cd; color: #856404; padding: 15px; border-radius: 12px; border-left: 10px solid #ffc107; margin-bottom: 15px; }
    .card-programar { background-color: #cfe2ff; color: #084298; padding: 15px; border-radius: 12px; border-left: 10px solid #0d6efd; margin-bottom: 15px; }
    .card-concluido { background-color: #d1e7dd; color: #0f5132; padding: 12px; border-radius: 10px; border-left: 10px solid #198754; margin-bottom: 10px; opacity: 0.7; }
    .btn-link { display: inline-block; padding: 5px 15px; background-color: #007bff; color: white !important; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('agenda_destaque.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS agenda (dia TEXT PRIMARY KEY, pauta TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS pautas_trabalho 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, link_ref TEXT, status TEXT, data_envio TEXT, prioridade TEXT)''')
    c.execute("PRAGMA table_info(pautas_trabalho)")
    cols = [col[1] for col in c.fetchall()]
    if 'prioridade' not in cols: c.execute("ALTER TABLE pautas_trabalho ADD COLUMN prioridade TEXT DEFAULT 'Normal'")
    if 'data_envio' not in cols: c.execute("ALTER TABLE pautas_trabalho ADD COLUMN data_envio TEXT")
    conn.commit(); conn.close()

init_db()

# --- 4. LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown('<div class="topo-titulo"><h1>Acesso Restrito</h1><p>Portal Destaque Toledo</p></div>', unsafe_allow_html=True)
    _, col2, _ = st.columns([1,1,1])
    with col2:
        with st.form("login"):
            u = st.text_input("Usuário").lower()
            s = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                if (u == "juan" and s == "juan123") or (u == "brayan" and s == "brayan123"):
                    st.session_state.autenticado = True; st.session_state.perfil = u; st.rerun()
                else: st.error("Usuário ou senha incorretos")
else:
    # --- 5. FUNÇÃO DE ARTE (EXATAMENTE O SEU PADRÃO ENVIADO) ---
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
            tam_f = 85
            while tam_f > 20:
                fonte = ImageFont.truetype(CAMINHO_FONTE, tam_f)
                linhas = textwrap.wrap(titulo, width=20) 
                if len(linhas) <= 3: break
                tam_f -= 2
            
            y_f = 811 - (len(linhas) * tam_f // 2)
            for lin in linhas:
                draw.text((488, y_f), lin, fill="black", font=fonte, anchor="mm")
                y_f += tam_f + 4
                
        else: # STORY
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

    def obter_noticias_site():
        try:
            res = requests.get("https://www.destaquetoledo.com.br/", headers=HEADERS, timeout=10).text
            soup = BeautifulSoup(res, "html.parser")
            noticias = []
            for a in soup.find_all("a", href=True):
                if ".html" in a['href'] and "/20" in a['href']:
                    t = a.get_text(strip=True)
                    if len(t) > 20: noticias.append({"titulo": t, "url": a['href']})
            return noticias[:15]
        except: return []

    # --- 6. INTERFACE ---
    st.markdown(f'<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1><p>Bem-vindo, {st.session_state.perfil.capitalize()}!</p></div>', unsafe_allow_html=True)

    if st.session_state.perfil == "juan":
        aba1, aba2, aba3 = st.tabs(["🎨 GERADOR DE ARTES", "📝 ENVIAR AO BRAYAN", "📅 AGENDA"])
        
        with aba1:
            c_l, c_w = st.columns([1, 2])
            with c_l:
                st.subheader("📰 Notícias")
                lista = obter_noticias_site()
                for i, n in enumerate(lista):
                    if st.button(n['titulo'], key=f"noticia_{i}"): st.session_state.url_ativa = n['url']
            with c_w:
                url = st.text_input("Link da matéria:", value=st.session_state.get('url_ativa', ''))
                if url:
                    col_a, col_b = st.columns(2)
                    if col_a.button("🖼️ GERAR FEED (QUADRADO)"):
                        img = processar_imagem_web(url, "FEED")
                        if img: st.image(img); buf=io.BytesIO(); img.save(buf,"JPEG"); st.download_button("Baixar Feed", buf.getvalue(), "feed.jpg")
                    if col_b.button("📱 GERAR STORY (VERTICAL)"):
                        img = processar_imagem_web(url, "STORY")
                        if img: st.image(img, width=250); buf=io.BytesIO(); img.save(buf,"JPEG"); st.download_button("Baixar Story", buf.getvalue(), "story.jpg")

        with aba2:
            st.subheader("🚀 Gerenciar Fila")
            with st.form("envio"):
                t_p = st.text_input("Título"); l_p = st.text_input("Link")
                prio = st.select_slider("Prioridade", options=["Programar", "Normal", "URGENTE"], value="Normal")
                if st.form_submit_button("Enviar ao Brayan"):
                    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
                    c.execute("INSERT INTO pautas_trabalho (titulo, link_ref, status, data_envio, prioridade) VALUES (?,?,'Pendente',?,?)",
                             (t_p, l_p, datetime.now().strftime("%H:%M"), prio))
                    conn.commit(); conn.close(); st.rerun()
            
            st.markdown("---")
            conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
            c.execute("SELECT * FROM pautas_trabalho ORDER BY id DESC LIMIT 10"); p_list = c.fetchall(); conn.close()
            for p in p_list:
                status_atual = p[3]
                prio_txt = str(p[5]) if p[5] else "Normal"
                cor_card = "card-concluido" if status_atual == "✅ Concluído" else ("card-urgente" if prio_txt == "URGENTE" else ("card-programar" if prio_txt == "Programar" else "card-normal"))
                st.markdown(f"<div class='{cor_card}'><b>{prio_txt}</b> | {p[4]} - {p[1]} <br> Status: {status_atual}</div>", unsafe_allow_html=True)
                if st.button(f"Excluir #{p[0]}", key=f"del_{p[0]}"):
                    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor(); c.execute("DELETE FROM pautas_trabalho WHERE id=?",(p[0],)); conn.commit(); conn.close(); st.rerun()

        with aba3:
            dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
            conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor(); c.execute("SELECT * FROM agenda"); p_ag = dict(c.fetchall()); conn.close()
            cols = st.columns(7)
            for i, d in enumerate(dias):
                with cols[i]:
                    nt = st.text_area(d, value=p_ag.get(d,""), height=300)
                    if nt != p_ag.get(d,""):
                        conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor(); c.execute("INSERT OR REPLACE INTO agenda (dia, pauta) VALUES (?,?)",(d,nt)); conn.commit(); conn.close(); st.toast(f"Salvo {d}")

    else: # PAINEL BRAYAN
        st.subheader("📋 Sua Fila de Trabalho")
        conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
        c.execute("SELECT * FROM pautas_trabalho WHERE status = 'Pendente' ORDER BY CASE WHEN prioridade='URGENTE' THEN 1 WHEN prioridade='Normal' THEN 2 ELSE 3 END"); p_br = c.fetchall(); conn.close()
        for pb in p_br:
            prio_br = str(pb[5]) if pb[5] else "Normal"
            cor_br = "card-urgente" if prio_br == "URGENTE" else ("card-programar" if prio_br == "Programar" else "card-normal")
            st.markdown(f"<div class='{cor_br}'><b>{prio_br.upper()}</b> - Enviado às {pb[4]}<br><span style='font-size:1.3rem'>{pb[1]}</span><br><a href='{pb[2]}' target='_blank' class='btn-link'>🔗 ACESSAR MATÉRIA</a></div>", unsafe_allow_html=True)
            if st.button("CONCLUÍDO", key=f"ok_{pb[0]}"):
                conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor(); c.execute("UPDATE pautas_trabalho SET status='✅ Concluído' WHERE id=?",(pb[0],)); conn.commit(); conn.close(); st.rerun()

    if st.sidebar.button("Sair"): st.session_state.autenticado = False; st.rerun()
