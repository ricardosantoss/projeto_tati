import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests

# 1. Configurações da Página
st.set_page_config(page_title="Sistema PEI - IFMT", layout="wide")

# Estilização IFMT
st.markdown("""
    <style>
    .stButton>button { background-color: #2f9e41; color: white; font-weight: bold; }
    h1 { color: #2f9e41; border-bottom: 3px solid #ed1c24; }
    .aluno-card { background-color: #ffffff; padding: 20px; border-radius: 10px; border-left: 5px solid #2f9e41; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# 2. Função IA (Maritalk)
def gerar_sugestao_pei(aluno_dados, docente, disciplina, conteudo):
    try:
        api_key = st.secrets["MARITALK_API_KEY"]
        url = "https://chat.maritaca.ai/api/chat/completions"
        headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
        
        prompt = f"""
        Você é um especialista em AEE do IFMT. Gere um plano adaptado para o aluno {aluno_dados['Nome do Estudante']}.
        Diagnóstico: {aluno_dados['(03) Necessidades Educacionais Específicas']}
        Dificuldades: {aluno_dados['(05) Dificuldades Apresentadas']}
        Habilidades: {aluno_dados['(04) Conhecimentos e Habilidades']}
        
        Disciplina: {disciplina}
        Conteúdo da aula: {conteudo}
        
        Escreva os itens: (07) Objetivos, (08) Conteúdo Adaptado, (09) Metodologia, (10) Avaliação e (11) Resultados.
        """
        
        data = {
            "model": "sabia-3",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1500
        }
        response = requests.post(url, headers=headers, json=data)
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Erro na IA: {e}"

# 3. Conexão e Limpeza
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read()
    
    # Remove espaços em branco dos nomes das colunas
    df.columns = [str(c).strip() for c in df.columns]
except Exception as e:
    st.error(f"Erro ao carregar planilha: {e}")
    st.stop()

# 4. Interface
st.title("🌿 Sistema PEI - IFMT")

# Definimos as variáveis com os nomes das colunas EXATOS da sua tabela
COL_NOME = 'Nome do Estudante'
COL_HIST = '(02) Histórico'
COL_NECESSIDADE = '(03) Necessidades Educacionais Específicas'
COL_HABILIDADE = '(04) Conhecimentos e Habilidades'
COL_DIFICULDADE = '(05) Dificuldades Apresentadas'
COL_ADAPTACAO = '(06) Adaptações Razoáveis e/ou Acessibilidades'

if not df.empty:
    # Verificação amigável de erro
    if COL_NOME not in df.columns:
        st.error(f"A coluna '{COL_NOME}' não foi encontrada.")
        st.write("Colunas que eu encontrei na sua planilha:", df.columns.tolist())
        st.info("💡 Dica: Renomeie as colunas no Google Sheets para ficarem iguais ao Anexo II.")
        st.stop()

    aluno_selecionado = st.selectbox("Selecione o Aluno:", ["Selecione..."] + df[COL_NOME].tolist())

    if aluno_selecionado != "Selecione...":
        dados = df[df[COL_NOME] == aluno_selecionado].iloc[0].to_dict()

        st.markdown(f"""
        <div class="aluno-card">
            <h3>Ficha Técnica: {aluno_selecionado}</h3>
            <p><b>Necessidades:</b> {dados.get(COL_NECESSIDADE, 'Não informado')}</p>
            <p><b>Dificuldades:</b> {dados.get(COL_DIFICULDADE, 'Não informado')}</p>
        </div>
        """, unsafe_allow_html=True)

        st.divider()
        
        docente = st.text_input("Nome do Docente:")
        materia = st.text_input("Componente Curricular:")
        conteudo = st.text_area("Conteúdo a ser ministrado:")

        if st.button("Gerar Plano Adaptado"):
            with st.spinner("IA criando proposta..."):
                resultado = gerar_sugestao_pei(dados, docente, materia, conteudo)
                st.session_state['rascunho'] = resultado

        if 'rascunho' in st.session_state:
            # Área de edição
            texto_editavel = st.text_area("Revise e edite o plano abaixo:", value=st.session_state['rascunho'], height=300)
            
            # Botão de Download
            st.download_button("📥 Baixar PEI (.txt)", texto_editavel, f"PEI_{aluno_selecionado}.txt")
