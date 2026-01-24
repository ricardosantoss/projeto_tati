import streamlit as st
import pandas as pd
import requests
import json

# Configurações da Página
st.set_page_config(page_title="Gerador de PEI - Maritalk", layout="wide")

# Título e Descrição
st.title("📝 Gerador de Plano de Ensino Individualizado (PEI)")
st.markdown("""
Este aplicativo utiliza a inteligência artificial **Maritalk** para gerar propostas de PEI 
baseadas nos dados dos alunos cadastrados em sua planilha do Google Sheets.
""")

# Sidebar para Configurações
with st.sidebar:
    st.header("Configurações")
    api_key = st.text_input("Maritalk API Key", type="password", help="Insira sua chave da API Maritalk")
    sheet_url = st.text_input("URL do Google Sheets (CSV)", help="Link da planilha exportada como CSV")
    
    st.divider()
    st.info("Dica: No Google Sheets, vá em Arquivo > Compartilhar > Publicar na Web e escolha o formato CSV.")

# Função para carregar dados do Google Sheets
@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar a planilha: {e}")
        return None

# Função para chamar a API do Maritalk
def generate_pei(aluno_data, api_key):
    url = "https://chat.maritaca.ai/api/chat/completions"
    
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    Você é um especialista em educação especial e inclusiva. 
    Gere um Plano de Ensino Individualizado (PEI) detalhado para o seguinte aluno:
    
    Nome: {aluno_data.get('Nome', 'N/A')}
    Idade: {aluno_data.get('Idade', 'N/A')}
    Diagnóstico: {aluno_data.get('Diagnóstico', 'N/A')}
    Dificuldades: {aluno_data.get('Dificuldades', 'N/A')}
    Pontos Fortes: {aluno_data.get('Pontos Fortes', 'N/A')}
    Objetivos Pedagógicos: {aluno_data.get('Objetivos Pedagógicos', 'N/A')}
    
    O PEI deve conter:
    1. Objetivos de Curto Prazo
    2. Adaptações Curriculares Necessárias
    3. Estratégias de Ensino Recomendadas
    4. Recursos de Apoio (Tecnologia Assistiva, Materiais, etc.)
    5. Critérios de Avaliação
    
    Responda em formato Markdown bem estruturado.
    """
    
    data = {
        "model": "sabia-3", 
        "messages": [
            {"role": "system", "content": "Você é um assistente especializado em educação inclusiva."},
            {"role": "user", "content": prompt}
        ],
        "do_sample": True,
        "max_tokens": 2000,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"Erro na API ({response.status_code}): {response.text}"
    except Exception as e:
        return f"Erro de conexão: {e}"

# Lógica Principal
if sheet_url:
    df = load_data(sheet_url)
    
    if df is not None:
        st.subheader("Alunos Cadastrados")
        st.dataframe(df, use_container_width=True)
        
        st.divider()
        
        st.subheader("Gerar PEI")
        if 'Nome' in df.columns:
            aluno_selecionado = st.selectbox("Selecione um aluno para gerar o PEI:", df['Nome'].tolist())
            
            if st.button("Gerar PEI com Maritalk"):
                if not api_key:
                    st.warning("Por favor, insira sua API Key do Maritalk na barra lateral.")
                else:
                    aluno_info = df[df['Nome'] == aluno_selecionado].iloc[0].to_dict()
                    
                    with st.spinner(f"Gerando PEI para {aluno_selecionado}..."):
                        resultado = generate_pei(aluno_info, api_key)
                        
                    st.markdown("---")
                    st.markdown(resultado)
                    
                    # Opção para baixar o PEI
                    st.download_button(
                        label="Baixar PEI como Texto",
                        data=resultado,
                        file_name=f"PEI_{aluno_selecionado.replace(' ', '_')}.md",
                        mime="text/markdown"
                    )
        else:
            st.error("A planilha deve conter uma coluna chamada 'Nome'.")
else:
    st.info("Aguardando o link da planilha do Google Sheets na barra lateral.")
    
    # Exemplo de estrutura esperada
    with st.expander("Veja a estrutura esperada da planilha"):
        st.write("A planilha deve conter as seguintes colunas:")
        st.code("Nome, Idade, Diagnóstico, Dificuldades, Pontos Fortes, Objetivos Pedagógicos")
