import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests

# Configurações da Página
st.set_page_config(page_title="Sistema PEI - IFMT", layout="wide", page_icon="🌿")

# Estilização IFMT (Verde e Vermelho)
st.markdown("""
    <style>
    .main {
        background-color: #f5f5f5;
    }
    .stButton>button {
        background-color: #2f9e41;
        color: white;
        border-radius: 5px;
    }
    .stSidebar {
        background-color: #ffffff;
    }
    h1 {
        color: #2f9e41;
        border-bottom: 2px solid #ed1c24;
    }
    .aluno-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #2f9e41;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# Função para chamar Maritalk (usando Secrets)
def call_maritalk(prompt):
    try:
        api_key = st.secrets["MARITALK_API_KEY"]
    except:
        st.error("Erro: Chave MARITALK_API_KEY não configurada nos Secrets.")
        return None

    url = "https://chat.maritaca.ai/api/chat/completions"
    headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
    data = {
        "model": "sabia-3",
        "messages": [
            {"role": "system", "content": "Você é um especialista em educação inclusiva do IFMT. Ajude professores a criarem PEIs e atividades adaptadas."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2000,
        "temperature": 0.2
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"Erro na API: {response.text}"
    except Exception as e:
        return f"Erro de conexão: {e}"

# Navegação
page = st.sidebar.radio("Navegação", ["Gerador de PEI", "Sugestão de Atividades"])

# Conexão com Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read()
except Exception as e:
    st.error("Erro ao conectar com a planilha. Verifique os Secrets.")
    st.stop()

if page == "Gerador de PEI":
    st.title("🌿 Gerador de PEI - IFMT")
    
    if 'Nome' in df.columns:
        aluno_nome = st.selectbox("Selecione o Aluno:", ["Selecione..."] + df['Nome'].tolist())
        
        if aluno_nome != "Selecione...":
            aluno_info = df[df['Nome'] == aluno_nome].iloc[0].to_dict()
            
            # Mostra dados apenas após seleção
            with st.container():
                st.markdown(f"""
                <div class="aluno-card">
                    <h3>Dados do Aluno: {aluno_nome}</h3>
                    <p><b>Diagnóstico:</b> {aluno_info.get('Diagnóstico', 'N/A')}</p>
                    <p><b>Dificuldades:</b> {aluno_info.get('Dificuldades', 'N/A')}</p>
                    <p><b>Pontos Fortes:</b> {aluno_info.get('Pontos Fortes', 'N/A')}</p>
                </div>
                """, unsafe_allow_html=True)
            
            st.divider()
            
            conteudo = st.text_area("Conteúdo/Tópico a ser ministrado:", placeholder="Ex: Equações do 2º grau, Revolução Francesa...")
            
            if st.button("Gerar PEI Adaptado"):
                if not conteudo:
                    st.warning("Por favor, informe o conteúdo que será ministrado.")
                else:
                    prompt = f"""
                    Gere um PEI (Plano de Ensino Individualizado) para o aluno {aluno_nome}.
                    Dados do aluno: {aluno_info}
                    Conteúdo a ser ministrado: {conteudo}
                    
                    O plano deve focar em como adaptar este conteúdo específico para as necessidades do aluno.
                    """
                    with st.spinner("Gerando PEI..."):
                        resultado = call_maritalk(prompt)
                        if resultado:
                            st.markdown("### 📄 PEI Sugerido")
                            st.markdown(resultado)
                            st.download_button("Baixar PEI (Markdown)", resultado, f"PEI_{aluno_nome}.md")
    else:
        st.error("Coluna 'Nome' não encontrada na planilha.")

elif page == "Sugestão de Atividades":
    st.title("💡 Sugestão de Atividades Adaptadas")
    
    aluno_nome = st.selectbox("Selecione o Aluno para a atividade:", ["Selecione..."] + df['Nome'].tolist())
    
    if aluno_nome != "Selecione...":
        aluno_info = df[df['Nome'] == aluno_nome].iloc[0].to_dict()
        conteudo_atv = st.text_input("Qual o tema da atividade?", placeholder="Ex: Frações, Ecossistemas...")
        
        if st.button("Propor Atividades"):
            if not conteudo_atv:
                st.warning("Informe o tema da atividade.")
            else:
                prompt_atv = f"""
                Com base no perfil do aluno {aluno_nome} ({aluno_info}), 
                proponha 3 atividades práticas e adaptadas sobre o tema: {conteudo_atv}.
                As atividades devem ser inclusivas e considerar os pontos fortes do aluno.
                """
                with st.spinner("Criando sugestões..."):
                    resultado_atv = call_maritalk(prompt_atv)
                    if resultado_atv:
                        st.markdown(resultado_atv)
                        st.download_button("Baixar Sugestões", resultado_atv, f"Atividades_{aluno_nome}.md")

# Rodapé
st.sidebar.divider()
st.sidebar.image("https://ifmt.edu.br/media/filer_public_thumbnails/filer_public/01/0e/010e6e8e-2e6e-4e1e-8e6e-010e6e8e2e6e/logo_ifmt.png__200x200_q85_subsampling-2.png", width=100)
st.sidebar.caption("Sistema de Apoio à Inclusão - IFMT")

