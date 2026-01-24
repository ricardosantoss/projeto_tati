import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests

# 1. Configurações da Página
st.set_page_config(page_title="Sistema PEI - IFMT", layout="wide")

# Estilização com as cores do IFMT
st.markdown("""
    <style>
    .main { background-color: #f9f9f9; }
    .stButton>button { background-color: #2f9e41; color: white; border-radius: 8px; height: 3em; width: 100%; font-weight: bold; }
    h1 { color: #2f9e41; border-bottom: 3px solid #ed1c24; }
    .aluno-box { background-color: white; padding: 20px; border-radius: 10px; border-left: 5px solid #2f9e41; box-shadow: 2px 2px 8px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# 2. Função para chamar a IA (Maritalk)
def call_maritalk(dados_aluno, docente, disciplina, conteudo):
    try:
        api_key = st.secrets["MARITALK_API_KEY"]
        url = "https://chat.maritaca.ai/api/chat/completions"
        headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
        
        prompt = f"""
        Você é um especialista em educação inclusiva do IFMT. 
        Gere os itens pedagógicos do PEI para o aluno {dados_aluno['Nome do Estudante']}.
        
        PERFIL DO ALUNO:
        - Necessidades: {dados_aluno['(03) Necessidades Educacionais Específicas']}
        - Habilidades: {dados_aluno['(04) Conhecimentos e Habilidades']}
        - Dificuldades: {dados_aluno['(05) Dificuldades Apresentadas']}
        
        DISCIPLINA: {disciplina}
        CONTEÚDO: {conteudo}

        Responda detalhadamente os seguintes itens do Anexo II:
        (07) OBJETIVOS ESPECÍFICOS:
        (08) CONTEÚDOS PROGRAMÁTICOS (ADAPTADOS):
        (09) METODOLOGIA:
        (10) AVALIAÇÃO:
        (11) RESULTADOS ESPERADOS:
        """
        
        data = {
            "model": "sabia-3",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        
        response = requests.post(url, headers=headers, json=data)
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Erro na conexão com a IA: {e}"

# 3. Carregamento de Dados
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read()
    
    # LIMPEZA CRÍTICA: Remove espaços extras nos nomes das colunas para evitar KeyError
    df.columns = df.columns.str.strip()
    
except Exception as e:
    st.error(f"Erro ao acessar a planilha: {e}")
    st.stop()

# 4. Interface Principal
st.title("🌿 Sistema de Elaboração de PEI - IFMT")
st.caption("Baseado no ANEXO II - PLANO EDUCACIONAL INDIVIDUALIZADO")

if not df.empty:
    # Verificação de segurança da coluna
    col_nome = 'Nome do Estudante'
    if col_nome not in df.columns:
        st.error(f"Coluna '{col_nome}' não encontrada. Colunas disponíveis: {df.columns.tolist()}")
        st.stop()

    aluno_selecionado = st.selectbox("Selecione o Estudante:", ["Selecione..."] + df[col_nome].tolist())

    if aluno_selecionado != "Selecione...":
        # Puxa os dados da linha do aluno
        aluno = df[df[col_nome] == aluno_selecionado].iloc[0].to_dict()

        with st.container():
            st.markdown(f"""
            <div class="aluno-box">
                <h4>(01) Dados do Estudante</h4>
                <p><b>Nome:</b> {aluno[col_nome]} | <b>Curso:</b> {aluno.get('Curso', 'N/A')}</p>
                <p><b>Necessidades:</b> {aluno.get('(03) Necessidades Educacionais Específicas', 'N/A')}</p>
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        
        # Inputs do Professor
        col1, col2 = st.columns(2)
        with col1:
            nome_docente = st.text_input("Nome do Docente:")
            materia = st.text_input("Componente Curricular:")
        with col2:
            tema_aula = st.text_area("Conteúdo Programático:")

        if st.button("✨ Gerar Proposta de Adaptação (IA)"):
            if not tema_aula:
                st.warning("Por favor, informe o conteúdo da aula.")
            else:
                with st.spinner("A IA está analisando o perfil e criando o plano..."):
                    sugestao = call_maritalk(aluno, nome_docente, materia, tema_aula)
                    st.session_state['texto_pei'] = sugestao

        # 5. Edição e Download
        if 'texto_pei' in st.session_state:
            st.subheader("📝 Revisão do Professor")
            st.info("Você pode editar o texto abaixo antes de gerar o documento final.")
            
            # Área de edição para o professor
            conteudo_editado = st.text_area("Edite os itens (07) a (11):", value=st.session_state['texto_pei'], height=400)

            # Estrutura final do documento para exportação
            documento_final = f"""
MINISTÉRIO DA EDUCAÇÃO
SECRETARIA DE EDUCAÇÃO PROFISSIONAL E TECNOLÓGICA
INSTITUTO FEDERAL DE EDUCAÇÃO, CIÊNCIA E TECNOLOGIA DE MATO GROSSO

ANEXO II - PLANO EDUCACIONAL INDIVIDUALIZADO (PEI)

(01) DADOS PESSOAIS
Nome do Estudante: {aluno[col_nome]}
Nome do Pai/Mãe ou responsável: {aluno.get('Nome do Pai/Mãe ou responsável', '')}
Telefone: {aluno.get('Telefone para contato', '')}
Nascimento: {aluno.get('Data do Nascimento', '')} | Idade: {aluno.get('Idade', '')}
Curso: {aluno.get('Curso', '')}
Componente Curricular: {materia}
Docente: {nome_docente}

(02) HISTÓRICO
{aluno.get('(02) Histórico', '')}

(03) NECESSIDADES EDUCACIONAIS ESPECÍFICAS
{aluno.get('(03) Necessidades Educacionais Específicas', '')}

(04/05) HABILIDADES E DIFICULDADES
Habilidades: {aluno.get('(04) Conhecimentos e Habilidades', '')}
Dificuldades: {aluno.get('(05) Dificuldades Apresentadas', '')}

(06) ADAPTAÇÕES RAZOÁVEIS
{aluno.get('(06) Adaptações Razoáveis e/ou Acessibilidades', '')}

------------------------------------------------------------------
PLANEJAMENTO PEDAGÓGICO (ITENS 07 A 11)
------------------------------------------------------------------
{conteudo_editado}

(14) ASSINATURAS
Assinatura do Docente: ___________________________
Assinatura da Coordenação: _______________________

Data: {pd.Timestamp.now().strftime('%d/%m/%Y')}
            """

            st.download_button(
                label="📥 Baixar PEI Pronto (.txt)",
                data=documento_final,
                file_name=f"PEI_{aluno_selecionado}.txt",
                mime="text/plain"
            )
else:
    st.error("A planilha está vazia ou não pôde ser lida.")
