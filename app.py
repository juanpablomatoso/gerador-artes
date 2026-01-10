import streamlit as st
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import textwrap
import io
import os
import sqlite3
from datetime import datetime

# --- CONFIGURAÇÃO E ESTILIZAÇÃO ---
st.set_page_config(page_title="Painel Destaque Toledo", layout="wide", page_icon="📸")

# Estilização Avançada com Cores por Status
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #f0f2f6; border-radius: 10px 10px 0 0; padding: 10px 20px;
    }
    .topo-titulo {
        text-align: center; padding: 25px;
        background: linear-gradient(90deg, #004a99 0%, #007bff 100%);
        color: white; border-radius: 15px; margin-bottom: 25px;
    }
    /* Cores de Status */
    .status-pendente { background-color: #fff3cd; color: #856404; padding: 10px; border-radius: 8px; border-left: 5px solid #ffc107; font-weight: bold; }
    .status-concluido { background-color: #d4edda; color: #155724; padding: 10px; border-radius: 8px; border-left: 5px solid #28a745; font-weight: bold; }
    .ajuda-texto { font-size: 0.85rem; color: #666; font-style: italic; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('agenda_destaque.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS agenda (dia TEXT PRIMARY KEY, pauta TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS pautas_trabalho 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, link_ref TEXT, status TEXT, data_envio TEXT)''')
    conn.commit(); conn.close()

init_db()

# --- FUNÇÕES AUXILIARES ---
def salvar_pauta_agenda(dia, pauta):
    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO agenda (dia, pauta) VALUES (?, ?)", (dia, pauta))
    conn.commit(); conn.close()

# --- LOGIN (Simplificado para o exemplo, mantenha sua lógica anterior) ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

# [Simulação de Login - Mantenha o bloco de login que te enviei antes]
# Para este exemplo, vamos direto ao painel do Juan para ver as cores:
st.session_state.autenticado = True 
st.session_state.perfil = "juan" 

if st.session_state.autenticado:
    st.markdown('<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1><p>Painel de Gestão Integrada</p></div>', unsafe_allow_html=True)
    
    aba_gerador, aba_fluxo, aba_agenda = st.tabs(["🎨 GERADOR DE ARTES", "📝 FLUXO BRAYAN", "📅 AGENDA"])

    # --- ABA 1: GERADOR (Preservado) ---
    with aba_gerador:
        st.markdown('<p class="ajuda-texto">💡 Selecione uma notícia ou cole o link para gerar artes para Instagram.</p>', unsafe_allow_html=True)
        # ... (Seu código original de artes entra aqui) ...

    # --- ABA 2: FLUXO COM BRAYAN (CORES E FEEDBACK) ---
    with aba_fluxo:
        col_envio, col_status = st.columns([1, 1.2])
        
        with col_envio:
            st.subheader("🚀 Enviar para o Brayan")
            st.markdown('<p class="ajuda-texto">Preencha os dados abaixo para que o Brayan saiba o que publicar no site.</p>', unsafe_allow_html=True)
            with st.form("form_pauta"):
                titulo_m = st.text_input("Título da Matéria", placeholder="Ex: Acidente na Av. Parigot...")
                obs_m = st.text_input("Link ou Observação", placeholder="Cole o link de referência aqui...")
                enviar = st.form_submit_button("✅ ENVIAR AGORA")
                
                if enviar and titulo_m:
                    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
                    data_atual = datetime.now().strftime("%d/%m %H:%M")
                    c.execute("INSERT INTO pautas_trabalho (titulo, link_ref, status, data_envio) VALUES (?, ?, '🟡 Pendente', ?)", 
                             (titulo_m, obs_m, data_atual))
                    conn.commit(); conn.close()
                    st.toast("Matéria enviada para a fila do Brayan!", icon="🚀")

        with col_status:
            st.subheader("📊 Status das Matérias")
            st.markdown('<p class="ajuda-texto">Acompanhe se o Brayan já postou as matérias enviadas.</p>', unsafe_allow_html=True)
            
            conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
            c.execute("SELECT * FROM pautas_trabalho ORDER BY id DESC LIMIT 10")
            pautas = c.fetchall(); conn.close()
            
            for p in pautas:
                classe_cor = "status-concluido" if p[3] == "✅ Concluído" else "status-pendente"
                status_texto = "CONCLUÍDO NO SITE" if p[3] == "✅ Concluído" else "AGUARDANDO BRAYAN"
                
                with st.container():
                    st.markdown(f"""
                        <div class="{classe_cor}">
                            <small>{p[4]}</small> | {status_texto}<br>
                            <span style='font-size:1.1rem'>{p[1]}</span>
                        </div>
                        <div style='margin-bottom:10px'></div>
                    """, unsafe_allow_html=True)

    # --- ABA 3: AGENDA (CORES POR DIA) ---
    with aba_agenda:
        st.markdown('<p class="ajuda-texto">💡 O que você digitar aqui é salvo na hora e ninguém mais altera.</p>', unsafe_allow_html=True)
        dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
        # Cores para cada dia para facilitar a vista
        cores_dias = ["#e3f2fd", "#fce4ec", "#f3e5f5", "#e8eaf6", "#e0f2f1", "#fffde7", "#efebe9"]
        cols = st.columns(7)
        
        conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
        c.execute("SELECT * FROM agenda"); pautas_db = dict(c.fetchall()); conn.close()

        for i, dia in enumerate(dias):
            with cols[i]:
                st.markdown(f"<div style='background-color:{cores_dias[i]}; padding:10px; border-radius:5px; text-align:center; font-weight:bold; color:black'>{dia}</div>", unsafe_allow_html=True)
                val = pautas_db.get(dia, "")
                txt = st.text_area(f"Pauta {dia}", value=val, key=f"ag_{dia}", height=300, label_visibility="collapsed")
                if txt != val:
                    salvar_pauta_agenda(dia, txt)
                    st.toast(f"Agenda de {dia} atualizada!")
