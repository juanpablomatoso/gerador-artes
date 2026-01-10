import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os
import sqlite3
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Painel Destaque Toledo", layout="wide", page_icon="🎨")

# --- 2. ESTILIZAÇÃO CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .topo-titulo {
        text-align: center; padding: 30px;
        background: linear-gradient(90deg, #004a99 0%, #007bff 100%);
        color: white; border-radius: 15px; margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .card-pauta {
        background-color: white; padding: 20px; border-radius: 12px;
        border-left: 6px solid #004a99; margin-bottom: 15px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .card-urgente { border-left: 6px solid #dc3545 !important; background-color: #fff5f5 !important; }
    .card-programar { border-left: 6px solid #ffc107 !important; background-color: #fffdf5 !important; }
    
    .tag-status {
        padding: 4px 12px; border-radius: 20px; font-size: 0.75rem;
        font-weight: bold; text-transform: uppercase;
    }
    .tag-urgente { background-color: #dc3545; color: white; }
    .tag-normal { background-color: #e9ecef; color: #495057; }
    .tag-programar { background-color: #ffc107; color: #000; }
    
    .obs-box {
        background-color: #e7f1ff; padding: 12px; border-radius: 8px;
        border: 1px dashed #004a99; margin-top: 10px; margin-bottom: 15px; font-style: italic;
    }
    .seo-box {
        background-color: #f1f8e9; padding: 15px; border-radius: 10px;
        border: 1px solid #c5e1a5; margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS agenda (dia TEXT PRIMARY KEY, pauta TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS pautas_trabalho 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, link_ref TEXT, status TEXT, data_envio TEXT, prioridade TEXT, observacao TEXT)''')
    # Nova tabela para Tarefas Internas
    c.execute('''CREATE TABLE IF NOT EXISTS tarefas_internas 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, tarefa TEXT, status TEXT)''')
    conn.commit(); conn.close()

init_db()

# --- 4. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown('<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1><p>Painel Administrativo</p></div>', unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_direto"):
            u = st.text_input("Usuário").lower().strip()
            s = st.text_input("Senha", type="password")
            st.checkbox("Mantenha-me conectado", value=True)
            if st.form_submit_button("ENTRAR NO SISTEMA", use_container_width=True):
                if (u == "juan" and s == "juan123") or (u == "brayan" and s == "brayan123"):
                    st.session_state.autenticado = True; st.session_state.perfil = u; st.rerun()
                else: st.error("Acesso negado.")
else:
    # --- BARRA LATERAL ---
    with st.sidebar:
        st.write(f"👤 Logado como: **{st.session_state.perfil.upper()}**")
        st.divider()
        if st.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state.autenticado = False; st.rerun()

    # --- FUNÇÕES DE ARTE (OCULTAS POR SEGURANÇA) ---
    CAMINHO_FONTE = "Shoika Bold.ttf"; TEMPLATE_FEED = "template_feed.png"; TEMPLATE_STORIE = "template_storie.png"; HEADERS = {"User-Agent": "Mozilla/5.0"}
    
    def processar_artes_integrado(url, tipo_solicitated):
        res_m = requests.get(url, headers=HEADERS).text; soup_m = BeautifulSoup(res_m, "html.parser"); titulo = soup_m.find("h1").get_text(strip=True); corpo = soup_m.find(class_="post-body") or soup_m; img_url = next(img.get("src") for img in corpo.find_all("img") if "logo" not in img.get("src").lower()); img_res = requests.get(img_url, headers=HEADERS); img_original = Image.open(io.BytesIO(img_res.content)).convert("RGBA"); larg_o, alt_o = img_original.size; prop_o = larg_o / alt_o
        if tipo_solicitated == "FEED":
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

    def buscar_ultimas():
        try:
            res = requests.get("https://www.destaquetoledo.com.br/", headers=HEADERS, timeout=10).text; soup = BeautifulSoup(res, "html.parser"); news = []
            for a in soup.find_all("a", href=True):
                if ".html" in a['href'] and "/20" in a['href']:
                    t = a.get_text(strip=True); news.append({"t": t, "u": a['href']})
            return news[:12]
        except: return []

    # --- INTERFACE PRINCIPAL ---
    st.markdown(f'<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1></div>', unsafe_allow_html=True)

    if st.session_state.perfil == "juan":
        tabs = st.tabs(["🎨 ARTES", "📝 FILA BRAYAN", "📅 AGENDA", "✅ TAREFAS"])
        
        with tabs[0]: # Gerador de Artes
            c1, col_preview = st.columns([1, 2])
            with c1:
                st.subheader("📰 Notícias")
                for i, item in enumerate(buscar_ultimas()):
                    if st.button(item['t'], key=f"btn_{i}", use_container_width=True): st.session_state.url_atual = item['u']
            with col_preview:
                url_f = st.text_input("Link da Matéria:", value=st.session_state.get('url_atual', ''))
                if url_f:
                    ca, cb = st.columns(2)
                    if ca.button("🖼️ FEED", use_container_width=True, type="primary"):
                        img = processar_artes_integrado(url_f, "FEED"); st.image(img); buf=io.BytesIO(); img.save(buf,"JPEG"); st.download_button("📥 BAIXAR FEED", buf.getvalue(), "feed.jpg")
                    if cb.button("📱 STORY", use_container_width=True):
                        img = processar_artes_integrado(url_f, "STORY"); st.image(img, width=280); buf=io.BytesIO(); img.save(buf,"JPEG"); st.download_button("📥 BAIXAR STORY", buf.getvalue(), "story.jpg")

        with tabs[1]: # Fila do Brayan
            with st.form("envio_pauta"):
                f_titulo = st.text_input("Título da Matéria")
                f_link = st.text_input("Link de Referência")
                f_obs = st.text_area("Instruções Adicionais")
                f_prio = st.select_slider("Urgência", options=["Normal", "Programar", "URGENTE"])
                if st.form_submit_button("🚀 ENVIAR PAUTA"):
                    hora = (datetime.utcnow() - timedelta(hours=3)).strftime("%H:%M")
                    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
                    c.execute("INSERT INTO pautas_trabalho (titulo, link_ref, status, data_envio, prioridade, observacao) VALUES (?,?,'Pendente',?,?,?)", (f_titulo, f_link, hora, f_prio, f_obs))
                    conn.commit(); conn.close(); st.success("Pauta enviada!"); st.rerun()

        with tabs[3]: # Tarefas Internas (Juan Visualiza e Cria)
            st.subheader("🛠️ Gerenciar Tarefas de Manutenção")
            nova_t = st.text_input("Nova Tarefa (Ex: Trocar Banner)")
            if st.button("Adicionar Tarefa"):
                conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
                c.execute("INSERT INTO tarefas_internas (tarefa, status) VALUES (?, 'Pendente')", (nova_t,))
                conn.commit(); conn.close(); st.rerun()
            
            st.divider()
            conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
            c.execute("SELECT * FROM tarefas_internas WHERE status = 'Pendente'")
            tarefas = c.fetchall(); conn.close()
            for t in tarefas:
                col_t, col_b = st.columns([4, 1])
                col_t.write(f"📌 {t[1]}")
                if col_b.button("Excluir", key=f"del_t_{t[0]}"):
                    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor(); c.execute("DELETE FROM tarefas_internas WHERE id=?", (t[0],)); conn.commit(); conn.close(); st.rerun()

    else: # PAINEL BRAYAN (FUNCIONALIDADES NOVAS)
        tabs_b = st.tabs(["📰 PAUTAS DO DIA", "✅ TAREFAS INTERNAS", "📝 CHECKLIST", "🚀 GERADOR TÍTULOS"])
        
        with tabs_b[0]: # Pautas
            conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
            c.execute("SELECT id, titulo, link_ref, data_envio, prioridade, observacao FROM pautas_trabalho WHERE status = 'Pendente' ORDER BY id DESC")
            p_br = c.fetchall(); conn.close()
            for pb in p_br:
                b_id, b_tit, b_link, b_hora, b_prio, b_obs = pb
                classe_cor = "card-urgente" if b_prio == "URGENTE" else "card-programar" if b_prio == "Programar" else ""
                tag_cor = "tag-urgente" if b_prio == "URGENTE" else "tag-programar" if b_prio == "Programar" else "tag-normal"
                st.markdown(f'<div class="card-pauta {classe_cor}"><span class="tag-status {tag_cor}">{b_prio}</span> | 🕒 {b_hora}<br><p style="font-size: 1.3rem; font-weight: bold; margin-top:10px;">{b_tit}</p></div>', unsafe_allow_html=True)
                if b_obs: st.markdown(f'<div class="obs-box"><b>Dica do Juan:</b> {b_obs}</div>', unsafe_allow_html=True)
                if b_link: st.link_button("🔗 VER REFERÊNCIA", b_link, use_container_width=True)
                if st.button("✅ CONCLUÍDO", key=f"ok_{b_id}", use_container_width=True, type="primary"):
                    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor(); c.execute("UPDATE pautas_trabalho SET status='✅ Concluído' WHERE id=?",(b_id,)); conn.commit(); conn.close(); st.rerun()
                st.divider()

        with tabs_b[1]: # Tarefas Internas (Manutenção do Site)
            st.subheader("🛠️ Tarefas de Manutenção")
            conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
            c.execute("SELECT * FROM tarefas_internas WHERE status = 'Pendente'")
            tarefas_b = c.fetchall(); conn.close()
            if not tarefas_b: st.success("Nenhuma tarefa de manutenção pendente!")
            for tb in tarefas_b:
                with st.expander(f"📌 {tb[1]}", expanded=True):
                    if st.button("Marcar como Feito", key=f"done_{tb[0]}"):
                        conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor(); c.execute("DELETE FROM tarefas_internas WHERE id=?", (tb[0],)); conn.commit(); conn.close(); st.rerun()

        with tabs_b[2]: # Checklist de Qualidade
            st.subheader("📋 Checklist de Postagem")
            st.info("Antes de clicar em 'Publicar' no site, verifique os itens abaixo:")
            st.checkbox("O título está chamativo e sem erros?")
            st.checkbox("A categoria da notícia está correta?")
            st.checkbox("A imagem de destaque tem boa qualidade?")
            st.checkbox("As tags (SEO) foram preenchidas?")
            st.checkbox("Os links internos (Leia também) foram adicionados?")

        with tabs_b[3]: # Gerador de Títulos SEO
            st.subheader("🚀 Otimizador de Títulos (SEO)")
            t_base = st.text_input("Digite o título simples da notícia:")
            if t_base:
                st.write("💡 **Sugestões para atrair mais cliques:**")
                st.success(f"🔥 **Urgente:** {t_base} - Veja os detalhes!")
                st.success(f"❓ Saiba tudo sobre: {t_base}")
                st.success(f"📍 Toledo: {t_base} (Entenda o caso)")
                st.success(f"😱 O que aconteceu em {t_base}? Confira agora!")
