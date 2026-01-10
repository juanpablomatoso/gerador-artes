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

# --- 2. ESTILIZAÇÃO CSS (PADRONIZADA E SEM CORES QUE DÃO ERRO) ---
st.markdown("""
    <style>
    .topo-titulo {
        text-align: center; padding: 20px;
        background: #004a99;
        color: white; border-radius: 15px; margin-bottom: 20px;
    }
    .card-pauta {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #ddd;
        margin-bottom: 15px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .tag-status {
        background-color: #f1f1f1;
        padding: 4px 10px;
        border-radius: 5px;
        font-weight: bold;
        color: #333;
        border: 1px solid #ccc;
    }
    .obs-box {
        background-color: #fff8e1;
        padding: 10px;
        border-left: 5px solid #ffc107;
        margin-top: 10px;
        font-size: 0.9rem;
    }
    .btn-link {
        display: inline-block;
        padding: 8px 15px;
        background-color: #007bff;
        color: white !important;
        text-decoration: none;
        border-radius: 5px;
        margin-top: 10px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. BANCO DE DADOS (ADICIONADO CAMPO OBSERVAÇÃO) ---
def init_db():
    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS agenda (dia TEXT PRIMARY KEY, pauta TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS pautas_trabalho 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, link_ref TEXT, status TEXT, data_envio TEXT, prioridade TEXT, observacao TEXT)''')
    # Verificar se a coluna observacao existe (para não dar erro em bancos antigos)
    c.execute("PRAGMA table_info(pautas_trabalho)")
    colunas = [col[1] for col in c.fetchall()]
    if 'observacao' not in colunas:
        c.execute("ALTER TABLE pautas_trabalho ADD COLUMN observacao TEXT")
    conn.commit(); conn.close()

init_db()

# --- 4. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown('<div class="topo-titulo"><h1>Acesso Restrito</h1></div>', unsafe_allow_html=True)
    _, col2, _ = st.columns([1,1,1])
    with col2:
        with st.form("login"):
            u = st.text_input("Usuário").lower()
            s = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                if (u == "juan" and s == "juan123") or (u == "brayan" and s == "brayan123"):
                    st.session_state.autenticado = True; st.session_state.perfil = u; st.rerun()
else:
    # --- 5. GERADOR DE ARTES (NÃO ALTERADO - PRESERVADO CONFORME SOLICITADO) ---
    CAMINHO_FONTE = "Shoika Bold.ttf"; TEMPLATE_FEED = "template_feed.png"; TEMPLATE_STORIE = "template_storie.png"; HEADERS = {"User-Agent": "Mozilla/5.0"}
    def processar_artes_integrado(url, tipo_solicitado):
        try:
            res_m = requests.get(url, headers=HEADERS).text; soup_m = BeautifulSoup(res_m, "html.parser"); titulo = soup_m.find("h1").get_text(strip=True); corpo = soup_m.find(class_="post-body") or soup_m; img_url = next(img.get("src") for img in corpo.find_all("img") if "logo" not in img.get("src").lower()); img_res = requests.get(img_url, headers=HEADERS); img_original = Image.open(io.BytesIO(img_res.content)).convert("RGBA"); larg_o, alt_o = img_original.size; prop_o = larg_o / alt_o
            if tipo_solicitado == "FEED":
                TAMANHO_FEED = 1000
                if prop_o > 1.0:
                    n_alt = TAMANHO_FEED; n_larg = int(n_alt * prop_o); img_f_redim = img_original.resize((n_larg, n_alt), Image.LANCZOS); margem = (n_larg - TAMANHO_FEED) // 2; fundo_f = img_f_redim.crop((margem, 0, margem + TAMANHO_FEED, TAMANHO_FEED))
                else:
                    n_larg = TAMANHO_FEED; n_alt = int(n_larg / prop_o); img_f_redim = img_original.resize((n_larg, n_alt), Image.LANCZOS); margem = (n_alt - TAMANHO_FEED) // 2; fundo_f = img_f_redim.crop((0, margem, TAMANHO_FEED, margem + TAMANHO_FEED))
                if os.path.exists(TEMPLATE_FEED): tmp_f = Image.open(TEMPLATE_FEED).convert("RGBA").resize((TAMANHO_FEED, TAMANHO_FEED)); fundo_f.alpha_composite(tmp_f)
                draw_f = ImageDraw.Draw(fundo_f); tam_f = 85
                while tam_f > 20:
                    fonte_f = ImageFont.truetype(CAMINHO_FONTE, tam_f); limite_f = int(662 / (fonte_f.getlength("W") * 0.55)); linhas_f = textwrap.wrap(titulo, width=max(10, limite_f)); alt_bloco_f = (len(linhas_f) * tam_f) + ((len(linhas_f)-1) * 4)
                    if alt_bloco_f <= 165 and len(linhas_f) <= 3: break
                    tam_f -= 1
                y_f = 811 - (alt_bloco_f // 2)
                for lin in linhas_f: larg_l = draw_f.textbbox((0, 0), lin, font=fonte_f)[2]; draw_f.text((488 - (larg_l // 2), y_f), lin, fill="black", font=fonte_f); y_f += tam_f + 4
                return fundo_f.convert("RGB")
            else: # STORY
                LARG_STORY, ALT_STORY = 940, 541; ratio_a = LARG_STORY / ALT_STORY
                if prop_o > ratio_a: ns_alt = ALT_STORY; ns_larg = int(ns_alt * prop_o)
                else: ns_larg = LARG_STORY; ns_alt = int(ns_larg / prop_o)
                img_s_redim = img_original.resize((ns_larg, ns_alt), Image.LANCZOS); l_cut = (ns_larg - LARG_STORY) / 2; t_cut = (ns_alt - ALT_STORY) / 2; img_s_final = img_s_redim.crop((l_cut, t_cut, l_cut + LARG_STORY, t_cut + ALT_STORY)); storie_canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 255)); storie_canvas.paste(img_s_final, (69, 504))
                if os.path.exists(TEMPLATE_STORIE): tmp_s = Image.open(TEMPLATE_STORIE).convert("RGBA").resize((1080, 1920)); storie_canvas.alpha_composite(tmp_s)
                draw_s = ImageDraw.Draw(storie_canvas); tam_s = 60
                while tam_s > 20:
                    fonte_s = ImageFont.truetype(CAMINHO_FONTE, tam_s); limite_s = int(912 / (fonte_s.getlength("W") * 0.55)); linhas_s = textwrap.wrap(titulo, width=max(10, limite_s)); alt_bloco_s = (len(linhas_s) * tam_s) + (len(linhas_s) * 10)
                    if alt_bloco_s <= 300 and len(linhas_s) <= 4: break
                    tam_s -= 2
                y_s = 1079
                for lin in linhas_s: draw_s.text((69, y_s), lin, fill="white", font=fonte_s); y_s += tam_s + 12
                return storie_canvas.convert("RGB")
        except: return None

    # --- 6. INTERFACE ---
    st.markdown(f'<div class="topo-titulo"><h1>PORTAL DESTAQUE TOLEDO</h1></div>', unsafe_allow_html=True)

    if st.session_state.perfil == "juan":
        t1, t2 = st.tabs(["🎨 GERADOR DE ARTES", "📝 FILA DO BRAYAN"])
        
        with t1:
            st.subheader("Gerar Imagem da Matéria")
            url_manual = st.text_input("Cole o link da matéria aqui:")
            if url_manual:
                col_a, col_b = st.columns(2)
                if col_a.button("Gerar Feed (Quadrado)"):
                    img = processar_artes_integrado(url_manual, "FEED")
                    if img: st.image(img); buf=io.BytesIO(); img.save(buf,"JPEG"); st.download_button("Baixar Feed", buf.getvalue(), "feed.jpg")
                if col_b.button("Gerar Story (Vertical)"):
                    img = processar_artes_integrado(url_manual, "STORY")
                    if img: st.image(img, width=250); buf=io.BytesIO(); img.save(buf,"JPEG"); st.download_button("Baixar Story", buf.getvalue(), "story.jpg")

        with t2:
            st.subheader("Mandar Nova Matéria")
            with st.form("envio_pauta"):
                tit = st.text_input("Título da Matéria")
                link_p = st.text_input("Link da Matéria")
                obs_p = st.text_area("Observações / Instruções Extras")
                urg = st.selectbox("Nível de Urgência", ["Normal", "URGENTE", "Programar"])
                if st.form_submit_button("Enviar para o Brayan"):
                    if tit:
                        h = datetime.now().strftime("%H:%M")
                        conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
                        c.execute("INSERT INTO pautas_trabalho (titulo, link_ref, status, data_envio, prioridade, observacao) VALUES (?,?,'Pendente',?,?,?)",
                                 (tit, link_p, h, urg, obs_p))
                        conn.commit(); conn.close(); st.success("Enviado com sucesso!"); st.rerun()

            st.markdown("---")
            st.subheader("Matérias Enviadas")
            conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
            c.execute("SELECT * FROM pautas_trabalho ORDER BY id DESC LIMIT 10"); p_list = c.fetchall(); conn.close()
            for p in p_list:
                with st.container():
                    st.markdown(f"""
                    <div class="card-pauta">
                        <span class="tag-status">{p[5]}</span> | 🕒 {p[4]}<br>
                        <b style='font-size:1.1rem'>{p[1]}</b><br>
                        <small>Status: {p[3]}</small>
                        {f'<div class="obs-box"><b>Obs:</b> {p[6]}</div>' if p[6] else ''}
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Excluir", key=f"del_{p[0]}"):
                        conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor(); c.execute("DELETE FROM pautas_trabalho WHERE id=?",(p[0],)); conn.commit(); conn.close(); st.rerun()

    else: # PAINEL BRAYAN
        st.subheader("📋 Lista de Trabalho")
        conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
        c.execute("SELECT * FROM pautas_trabalho WHERE status = 'Pendente' ORDER BY id DESC")
        p_br = c.fetchall(); conn.close()
        
        if not p_br:
            st.info("Nenhuma matéria pendente no momento.")

        for pb in p_br:
            st.markdown(f"""
                <div class="card-pauta">
                    <span class="tag-status">{pb[5]}</span> | Enviado às: {pb[4]}<br>
                    <p style='font-size: 1.3rem; font-weight: bold; margin-top:10px;'>{pb[1]}</p>
                    {f'<div class="obs-box"><b>Dica do Juan:</b> {pb[6]}</div>' if pb[6] else ''}
                    <a href='{pb[2]}' target='_blank' class='btn-link'>🔗 ABRIR MATÉRIA NO SITE</a>
                </div>
            """, unsafe_allow_html=True)
            if st.button("CONCLUÍDO / POSTADO", key=f"ok_{pb[0]}"):
                conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor(); c.execute("UPDATE pautas_trabalho SET status='✅ Concluído' WHERE id=?",(pb[0],)); conn.commit(); conn.close(); st.rerun()

    if st.sidebar.button("Sair"): st.session_state.autenticado = False; st.rerun()
