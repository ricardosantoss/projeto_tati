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

# 2. Conexão e Carregamento (COM LIMPEZA DE CACHE)
try:
    # O segredo está aqui: ttl=0 faz com que ele não guarde cache e leia sempre o novo
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Se você tiver mais de uma aba, coloque o nome da aba correta em worksheet="NomeDaAba"
    df = conn.read(ttl=0) 
    
    # Limpeza de nomes de colunas (remove espaços extras)
    df.columns = [str(c).strip() for c in df.columns]
except Exception as e:
    st.error(f"Erro ao carregar planilha: {e}")
    st.stop()

# 3. Mapeamento das Colunas (Exatamente como na sua imagem do Anexo II)
COL_NOME = 'Nome do Estudante'
COL_HIST = '(02) Histórico'
COL_NECESSIDADE = '(03) Necessidades Educacionais Específicas'
COL_HABILIDADE = '(04) Conhecimentos e Habilidades'
COL_DIFICULDADE = '(05) Dificuldades Apresentadas'
COL_ADAPTACAO = '(06) Adaptações Razoáveis e/ou Acessibilidades'

# 4. Interface Principal
st.title("🌿 Sistema PEI - IFMT")

# Verificação se a coluna existe (para evitar o KeyError)
if COL_NOME not in df.columns:
    st.error(f"⚠️ A coluna '{COL_NOME}' ainda não foi detectada.")
    st.write("Colunas atuais que o sistema está lendo:", df.columns.tolist())
    st.info("💡 Se você acabou de alterar a planilha, tente clicar nos três pontinhos no canto superior direito do app e escolha 'Clear Cache'.")
    st.stop()

aluno_selecionado = st.selectbox("Selecione o Aluno:", ["Selecione..."] + df[COL_NOME].tolist())

if aluno_selecionado != "Selecione...":
    # Localiza os dados do aluno
    dados = df[df[COL_NOME] == aluno_selecionado].iloc[0].to_dict()

    with st.container():
        st.markdown(f"""
        <div class="aluno-card">
            <h3>Ficha Técnica: {aluno_selecionado}</h3>
            <p><b>(03) Necessidades:</b> {dados.get(COL_NECESSIDADE, 'Dado não encontrado')}</p>
            <p><b>(05) Dificuldades:</b> {dados.get(COL_DIFICULDADE, 'Dado não encontrado')}</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    
    # Campos para o professor preencher
    col1, col2 = st.columns(2)
    with col1:
        docente = st.text_input("Nome do Docente:")
        materia = st.text_input("Componente Curricular:")
    with col2:
        tema = st.text_area("Conteúdo/Tópico da Aula:")

    if st.button("Gerar Plano com IA"):
        # Aqui entra a chamada da Maritalk (conforme os códigos anteriores)
        # Vamos simular a geração para o exemplo:
        prompt = f"Gere um PEI para {aluno_selecionado} sobre {tema}. Necessidades: {dados.get(COL_NECESSIDADE)}"
        st.session_state['rascunho'] = "Texto gerado pela IA..." 

    if 'rascunho' in st.session_state:
        # Permite edição antes de baixar
        texto_editado = st.text_area("Revise e finalize o texto:", value=st.session_state['rascunho'], height=300)
        st.download_button("📥 Baixar PEI Final", texto_editado, f"PEI_{aluno_selecionado}.txt")
