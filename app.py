import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os
import sqlite3
from datetime import datetime, timedelta
import google.generativeai as genai

# --- CONFIGURAÇÃO DA IA (GEMINI) ---
# Substitua pelo seu código de API para funcionar
genai.configure(api_key="SUA_CHAVE_API_AQUI")
model = genai.GenerativeModel('gemini-pro')

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Painel Destaque Toledo", layout="wide", page_icon="🎨")

# --- 2. ESTILIZAÇÃO CSS PROFISSIONAL (SUAS CORES ORIGINAIS) ---
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
    .card-urgente { border-left: 6px solid #dc3545; background-color: #fff5f5; }
    .card-programar { border-left: 6px solid #ffc107; background-color: #fffdf5; }
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
    .boas-vindas {
        font-size: 1.5rem; font-weight: bold; color: #004a99; margin-bottom: 10px;
    }
    .descricao-aba {
        color: #666; font-size: 0.95rem; margin-bottom: 20px; line-height: 1.4;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS agenda (dia TEXT PRIMARY KEY, pauta TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS pautas_trabalho 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, link_ref TEXT, status TEXT, data_envio TEXT, prioridade TEXT, observacao TEXT)''')
    # Tabela de Tarefas Internas
    c.execute('''CREATE TABLE IF NOT EXISTS tarefas_sistema 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, tarefa TEXT, status TEXT, recorrencia TEXT, autor TEXT)''')
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
            if st.form_submit_button("ENTRAR NO SISTEMA", use_container_width=True):
                if (u == "juan" and s == "juan123") or (u == "brayan" and s == "brayan123"):
                    st.session_state.autenticado = True; st.session_state.perfil = u; st.rerun()
                else: st.error("Acesso negado.")
else:
    # --- 5. FUNÇÕES AUXILIARES ---
    def gerar_titulos_gemini(tema):
        try:
            prompt = f"Gere 5 títulos de notícias virais e com SEO para o portal Destaque Toledo sobre: {tema}. Use gatilhos mentais e urgência."
            response = model.generate_content(prompt)
            return response.text.split('\n')
        except:
            return ["⚠️ Erro: Configure sua API Key do Gemini no código."]

    # (Suas funções processar_artes e buscar_ultimas aqui permanecem iguais)
    # [Omitidas para brevidade, mas devem ser mantidas no seu arquivo]

    # --- 6. INTERFACE INTERNA ---
    st.markdown(f'<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1></div>', unsafe_allow_html=True)

    # DEFINIÇÃO DAS ABAS PARA AMBOS
    if st.session_state.perfil == "juan":
        tabs = st.tabs(["🎨 GERADOR DE ARTES", "📝 FILA DO BRAYAN", "🛠️ TAREFAS INTERNAS", "📅 AGENDA"])
    else:
        tabs = st.tabs(["📰 MINHAS PAUTAS", "🛠️ TAREFAS INTERNAS", "🚀 GERADOR DE TÍTULOS IA"])

    # --- ABA TAREFAS (COMUM A AMBOS) ---
    with tabs[2 if st.session_state.perfil == "juan" else 1]:
        st.markdown('<p class="descricao-aba">Manutenção do site, banners e tarefas recorrentes.</p>', unsafe_allow_html=True)
        
        with st.form("nova_tarefa"):
            col_t1, col_t2 = st.columns([3, 1])
            t_nome = col_t1.text_input("Descrição da Tarefa")
            t_rec = col_t2.selectbox("Repetição", ["Única", "Diária", "Segunda", "Terça", "Quarta", "Quinta", "Sexta"])
            if st.form_submit_button("CADASTRAR TAREFA", use_container_width=True):
                if t_nome:
                    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
                    c.execute("INSERT INTO tarefas_sistema (tarefa, status, recorrencia, autor) VALUES (?, 'Pendente', ?, ?)", (t_nome, t_rec, st.session_state.perfil))
                    conn.commit(); conn.close(); st.rerun()

        st.divider()
        conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
        c.execute("SELECT * FROM tarefas_sistema WHERE status = 'Pendente'")
        tarefas = c.fetchall(); conn.close()
        
        for t in tarefas:
            with st.container():
                c_t1, c_t2 = st.columns([4, 1])
                c_t1.markdown(f"📌 **{t[1]}** | <small>Recorrência: {t[3]}</small>", unsafe_allow_html=True)
                if c_t2.button("Concluir", key=f"btn_t_{t[0]}"):
                    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
                    c.execute("UPDATE tarefas_sistema SET status = 'Concluído' WHERE id = ?", (t[0],))
                    conn.commit(); conn.close(); st.rerun()

    # --- ABA GERADOR DE TÍTULOS IA (EXCLUSIVA BRAYAN OU JUAN) ---
    if st.session_state.perfil == "brayan":
        with tabs[2]:
            st.subheader("🤖 Gerador de Títulos com Inteligência Artificial")
            tema = st.text_input("Digite o assunto da notícia (Ex: Acidente na Av. Maripá)")
            if st.button("GERAR TÍTULOS PROFISSIONAIS"):
                if tema:
                    sugestoes = gerar_titulos_gemini(tema)
                    for s in sugestoes:
                        if s.strip(): st.info(s)
                else: st.warning("Digite um assunto primeiro.")

    # (Mantenha o restante do código da Fila do Brayan e Artes conforme o seu original)

    with st.sidebar:
        st.write(f"Logado como: **{st.session_state.perfil.upper()}**")
        if st.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state.autenticado = False; st.rerun()
