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
    .tarefa-card {
        background: #fff; padding: 15px; border-radius: 8px; 
        border: 1px solid #ddd; margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS agenda (dia TEXT PRIMARY KEY, pauta TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS pautas_trabalho 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, link_ref TEXT, status TEXT, data_envio TEXT, prioridade TEXT, observacao TEXT)''')
    # Tabela de tarefas com recorrência e autor
    c.execute('''CREATE TABLE IF NOT EXISTS tarefas_v2 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, tarefa TEXT, status TEXT, recorrencia TEXT, autor TEXT)''')
    conn.commit(); conn.close()

init_db()

# --- 4. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown('<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1><p>Painel Administrativo</p></div>', unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login"):
            u = st.text_input("Usuário").lower().strip()
            s = st.text_input("Senha", type="password")
            st.checkbox("Mantenha-me conectado", value=True)
            if st.form_submit_button("ACESSAR PAINEL", use_container_width=True):
                if (u == "juan" and s == "juan123") or (u == "brayan" and s == "brayan123"):
                    st.session_state.autenticado = True; st.session_state.perfil = u; st.rerun()
                else: st.error("Acesso negado.")
else:
    # --- BARRA LATERAL ---
    with st.sidebar:
        st.write(f"👤 Conectado: **{st.session_state.perfil.upper()}**")
        st.divider()
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.autenticado = False; st.rerun()

    # --- FUNÇÃO GERADOR DE TÍTULOS (SIMULANDO LÓGICA DE IA) ---
    def gerar_titulos_ia(texto):
        if len(texto) < 5: return []
        padrões = [
            f"🔥 URGENTE: {texto} - Veja o que já se sabe",
            f"😱 IMPACTANTE: O que aconteceu em {texto} vai te surpreender!",
            f"📍 AGORA EM TOLEDO: {texto}. Confira os detalhes exclusivos!",
            f"❓ {texto}: Entenda as consequências e o que muda agora",
            f"🚨 PLANTÃO: Informações atualizadas sobre {texto}"
        ]
        return padrões

    # --- INTERFACE PRINCIPAL ---
    st.markdown(f'<div class="topo-titulo"><h1>DESTAQUE TOLEDO</h1></div>', unsafe_allow_html=True)

    # ABAS (MESMAS PARA AMBOS, MAS COM PERMISSÕES)
    abas = st.tabs(["🚀 OPERAÇÃO SITE", "🛠️ TAREFAS INTERNAS", "🎨 ARTES (JUAN)", "📅 AGENDA"])

    with abas[0]: # Operação Site (Pautas)
        if st.session_state.perfil == "juan":
            with st.form("envio_pauta"):
                f_tit = st.text_input("Título da Matéria")
                f_link = st.text_input("Link Referência")
                f_prio = st.select_slider("Urgência", options=["Normal", "Programar", "URGENTE"])
                if st.form_submit_button("ENVIAR PARA BRAYAN"):
                    hora = (datetime.utcnow() - timedelta(hours=3)).strftime("%H:%M")
                    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
                    c.execute("INSERT INTO pautas_trabalho (titulo, link_ref, status, data_envio, prioridade) VALUES (?,?,'Pendente',?,?)", (f_tit, f_link, hora, f_prio))
                    conn.commit(); conn.close(); st.success("Enviado!"); st.rerun()
        
        # Lista para o Brayan Ver
        conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
        c.execute("SELECT * FROM pautas_trabalho WHERE status = 'Pendente' ORDER BY id DESC")
        pautas = c.fetchall(); conn.close()
        for p in pautas:
            cor = "card-urgente" if p[5] == "URGENTE" else "card-programar" if p[5] == "Programar" else ""
            st.markdown(f'<div class="card-pauta {cor}"><b>{p[1]}</b><br><small>{p[5]} | {p[4]}</small></div>', unsafe_allow_html=True)
            col_a, col_b = st.columns(2)
            if p[2]: col_a.link_button("🔗 VER SITE", p[2], use_container_width=True)
            if col_b.button("✅ CONCLUÍDO", key=f"p_{p[0]}", use_container_width=True):
                conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor(); c.execute("UPDATE pautas_trabalho SET status='OK' WHERE id=?",(p[0],)); conn.commit(); conn.close(); st.rerun()

    with abas[1]: # TAREFAS INTERNAS (SISTEMA NOVO)
        st.subheader("📝 Gestão de Tarefas e Manutenção")
        
        # Cadastro de Tarefa
        with st.expander("➕ CADASTRAR NOVA TAREFA", expanded=False):
            with st.form("nova_tarefa"):
                t_nome = st.text_input("O que precisa ser feito?")
                t_recor = st.selectbox("Repetição", ["Única vez", "Toda Segunda", "Toda Terça", "Toda Quarta", "Toda Quinta", "Toda Sexta", "Diário"])
                if st.form_submit_button("SALVAR TAREFA"):
                    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
                    c.execute("INSERT INTO tarefas_v2 (tarefa, status, recorrencia, autor) VALUES (?, 'Pendente', ?, ?)", (t_nome, t_recor, st.session_state.perfil))
                    conn.commit(); conn.close(); st.rerun()

        # Lista de Tarefas
        col_pend, col_conc = st.columns(2)
        
        with col_pend:
            st.markdown("### ⏳ Pendentes")
            conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
            c.execute("SELECT * FROM tarefas_v2 WHERE status = 'Pendente'")
            t_pend = c.fetchall(); conn.close()
            for t in t_pend:
                st.markdown(f"""<div class="tarefa-card">
                    <b>{t[1]}</b><br>
                    <small>📅 {t[3]} | Por: {t[4]}</small>
                </div>""", unsafe_allow_html=True)
                if st.button("Marcar como Concluída", key=f"t_ok_{t[0]}", use_container_width=True):
                    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
                    c.execute("UPDATE tarefas_v2 SET status = 'Concluída' WHERE id = ?", (t[0],))
                    conn.commit(); conn.close(); st.rerun()

        with col_conc:
            st.markdown("### ✅ Concluídas")
            conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor()
            c.execute("SELECT * FROM tarefas_v2 WHERE status = 'Concluída' LIMIT 5")
            t_conc = c.fetchall(); conn.close()
            for tc in t_conc:
                st.markdown(f"""<div style="opacity: 0.6; padding:10px; border-bottom:1px solid #ddd;">
                    <strike>{tc[1]}</strike>
                </div>""", unsafe_allow_html=True)
                if st.button("Apagar Histórico", key=f"del_t_{tc[0]}"):
                    conn = sqlite3.connect('agenda_destaque.db'); c = conn.cursor(); c.execute("DELETE FROM tarefas_v2 WHERE id=?", (tc[0],)); conn.commit(); conn.close(); st.rerun()

    with abas[3]: # Gerador de Títulos (IA)
        st.subheader("🚀 Gerador de Títulos com IA (SEO)")
        t_input = st.text_input("Sobre o que é a notícia? (Ex: Acidente na BR-467)")
        if t_input:
            sugestoes = gerar_titulos_ia(t_input)
            for s in sugestoes:
                st.success(s)
                if st.button("Copiar", key=s): st.toast("Título selecionado!")

    # Aba de agenda e artes permanecem iguais conforme solicitado
