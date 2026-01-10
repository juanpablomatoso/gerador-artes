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

# --- 2. SISTEMA DE LOGIN (NOVO) ---
def login():
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        st.markdown('<div class="topo-titulo"><h1>Acesso Restrito</h1><p>Portal Destaque Toledo</p></div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,1,1])
        with col2:
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            if st.button("Entrar"):
                # Defina aqui as senhas que desejar
                if usuario.lower() == "juan" and senha == "juan123":
                    st.session_state.autenticado = True
                    st.session_state.perfil = "juan"
                    st.rerun()
                elif usuario.lower() == "brayan" and senha == "brayan123":
                    st.session_state.autenticado = True
                    st.session_state.perfil = "brayan"
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos")
        return False
    return True

# --- 3. BANCO DE DADOS (Preservado e Expandido) ---
def init_db():
    conn = sqlite3.connect('agenda_destaque.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS agenda (dia TEXT PRIMARY KEY, pauta TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS pautas_trabalho 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, link_ref TEXT, 
                  status TEXT, checklist_feed INTEGER, checklist_story INTEGER)''')
    conn.commit() ; conn.close()

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

# Inicialização
init_db()
pautas_salvas = carregar_pautas()

# Só executa o resto se estiver logado
if login():
    
    # Botão de Logout na Sidebar
    st.sidebar.write(f"Logado como: **{st.session_state.perfil.capitalize()}**")
    if st.sidebar.button("Sair"):
        st.session_state.autenticado = False
        st.rerun()

    # --- ESTILIZAÇÃO CSS (Inalterada) ---
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
        .card-pauta { background: white; padding: 15px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 10px; color: black; }
        </style>
        """, unsafe_allow_html=True)

    # --- FUNÇÕES CORE (Geração de Artes - INTOCADAS) ---
    CAMINHO_FONTE = "Shoika Bold.ttf"
    TEMPLATE_FEED = "template_feed.png"
    TEMPLATE_STORIE = "template_storie.png"
    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # [Aqui ficam as suas funções obter_lista_noticias e processar_artes_web exatamente como estão no seu arquivo]

    st.markdown(f'<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1><p>Bem-vindo, {st.session_state.perfil.capitalize()}</p></div>', unsafe_allow_html=True)

    # --- DEFINIÇÃO DE ABAS POR PERFIL ---
    if st.session_state.perfil == "juan":
        abas = st.tabs(["🎨 GERADOR DE ARTES", "📝 FLUXO BRAYAN", "📅 AGENDA SEMANAL", "🔗 LINKS ÚTEIS"])
    else:
        # Brayan só vê o Fluxo e os Links
        abas = st.tabs(["📝 MINHA FILA DE TRABALHO", "🔗 LINKS ÚTEIS"])

    # --- LÓGICA DAS ABAS PARA O JUAN ---
    if st.session_state.perfil == "juan":
        with abas[0]: # Gerador
            # [Seu código do gerador aqui...]
            pass 
        with abas[1]: # Fluxo
            # [Seu código de enviar pauta aqui...]
            pass
        with abas[2]: # Agenda
            # [Seu código da agenda aqui...]
            pass
        with abas[3]: # Links
            # [Seu código de links aqui...]
            pass

    # --- LÓGICA DAS ABAS PARA O BRAYAN ---
    else:
        with abas[0]: # Fila do Brayan
            st.markdown("### 📋 Matérias para Publicar (Enviadas por Juan)")
            # Mostra as pautas mas o Brayan só pode marcar como concluído
            conn = sqlite3.connect('agenda_destaque.db')
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pautas_trabalho WHERE status != '✅ Concluído' ORDER BY id DESC")
            pautas = cursor.fetchall()
            conn.close()
            for p in pautas:
                st.markdown(f"<div class='card-pauta'><b>📌 {p[1]}</b><br>Ref: {p[2]}</div>", unsafe_allow_html=True)
                if st.button(f"Concluí a Postagem", key=f"brayan_pub_{p[0]}"):
                    atualizar_status_pauta(p[0], "✅ Concluído")
                    st.rerun()
        with abas[1]: # Links
             st.info("🌐 **LINKS DE ACESSO RÁPIDO**")
             st.write("- [Painel Blogger](https://www.blogger.com)")
