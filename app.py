import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests

# Configurações da Página
st.set_page_config(page_title="Gerador de PEI - Maritalk", layout="wide")

# Título e Descrição
st.title("📝 Gerador de PEI (Tabela Google Sheets)")
st.markdown("""
Este app conecta diretamente à sua planilha do Google Sheets. 
Você pode visualizar os alunos na tabela abaixo e gerar o PEI usando o Maritalk.
""")

# Sidebar para Configurações de API
with st.sidebar:
    st.header("Configurações")
    api_key = st.text_input("Maritalk API Key", type="password", help="Insira sua chave da API Maritalk")
    
    st.divider()
    st.info("""
    **Como conectar o Sheets:**
    No Streamlit Cloud, você precisará configurar o `secrets.toml` com a URL da sua planilha.
    """)

# Conexão com Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Tenta ler a planilha configurada nos secrets ou via parâmetro
    df = conn.read()
    
    if df is not None:
        st.subheader("📋 Tabela de Alunos")
        
        # Exibe a tabela (editável se desejar, mas aqui apenas visualização)
        st.dataframe(df, use_container_width=True)
        
        st.divider()
        
        # Seleção de Aluno para PEI
        if 'Nome' in df.columns:
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.subheader("Gerar Plano")
                aluno_selecionado = st.selectbox("Selecione o aluno:", df['Nome'].tolist())
                btn_gerar = st.button("Gerar PEI com Maritalk")
            
            if btn_gerar:
                if not api_key:
                    st.warning("⚠️ Insira sua API Key do Maritalk na barra lateral.")
                else:
                    aluno_info = df[df['Nome'] == aluno_selecionado].iloc[0].to_dict()
                    
                    with st.spinner(f"🤖 Maritalk processando PEI para {aluno_selecionado}..."):
                        # Função de chamada à API (mesma lógica anterior)
                        url = "https://chat.maritaca.ai/api/chat/completions"
                        headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
                        
                        prompt = f"Gere um PEI detalhado para o aluno: {aluno_info}. Inclua objetivos, adaptações e estratégias."
                        
                        data = {
                            "model": "sabia-3",
                            "messages": [
                                {"role": "system", "content": "Você é um especialista em educação inclusiva."},
                                {"role": "user", "content": prompt}
                            ],
                            "max_tokens": 2000
                        }
                        
                        try:
                            response = requests.post(url, headers=headers, json=data)
                            if response.status_code == 200:
                                resultado = response.json()['choices'][0]['message']['content']
                                with col2:
                                    st.markdown("### PEI Gerado")
                                    st.markdown(resultado)
                                    st.download_button("Baixar PEI", resultado, f"PEI_{aluno_selecionado}.md")
                            else:
                                st.error(f"Erro na API: {response.text}")
                        except Exception as e:
                            st.error(f"Erro de conexão: {e}")
        else:
            st.error("A planilha precisa ter uma coluna chamada 'Nome'.")

except Exception as e:
    st.warning("Aguardando configuração da conexão com Google Sheets.")
    st.info("Para testar localmente, adicione a URL da planilha no arquivo `.streamlit/secrets.toml`.")
    with st.expander("Exemplo de configuração do Secrets"):
        st.code("""
[connections.gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/SUA_PLANILHA_ID"
        """)

