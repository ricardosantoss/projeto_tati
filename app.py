import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests

# 1. Configurações Iniciais e Estilo
st.set_page_config(page_title="Sistema PEI - IFMT", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { background-color: #2f9e41; color: white; font-weight: bold; border-radius: 8px; }
    h1 { color: #2f9e41; border-bottom: 3px solid #ed1c24; padding-bottom: 10px; }
    .status-card { background-color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #2f9e41; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# 2. Função de Integração com a IA (Maritalk)
def gerar_sugestao_pei(dados_aluno, docente, disciplina, conteudo):
    try:
        api_key = st.secrets["MARITALK_API_KEY"]
        url = "https://chat.maritaca.ai/api/chat/completions"
        headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
        
        prompt = f"""
        Você é um especialista em educação inclusiva do IFMT. 
        Com base nos dados abaixo, complete os itens 07, 08, 09, 10 e 11 do PEI.
        
        DADOS DO ALUNO:
        - Nome: {dados_aluno['Nome do Estudante']}
        - Necessidades: {dados_aluno['(03) Necessidades Educacionais Específicas']}
        - Habilidades: {dados_aluno['(04) Conhecimentos e Habilidades']}
        - Dificuldades: {dados_aluno['(05) Dificuldades Apresentadas']}
        
        CONTEXTO DA AULA:
        - Professor: {docente}
        - Disciplina: {disciplina}
        - Conteúdo a ser ensinado: {conteudo}
        
        Responda de forma técnica, pedagógica e estruturada para cada item (07 a 11).
        """
        
        data = {
            "model": "sabia-3",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1500
        }
        
        response = requests.post(url, headers=headers, json=data)
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Erro ao gerar sugestão: {e}"

# 3. Conexão com a Planilha
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read()
except:
    st.error("Erro ao conectar à planilha. Verifique suas credenciais nos Secrets.")
    st.stop()

# 4. Interface do Usuário
st.title("🌿 Gerador de PEI - IFMT (Anexo II)")

if not df.empty:
    # Seleção do Aluno (Coluna: Nome do Estudante)
    lista_alunos = df['Nome do Estudante'].tolist()
    aluno_selecionado = st.selectbox("Escolha o estudante para gerar o PEI:", ["Selecione..."] + lista_alunos)

    if aluno_selecionado != "Selecione...":
        # Extrai a linha do aluno
        dados = df[df['Nome do Estudante'] == aluno_selecionado].iloc[0].to_dict()

        # Exibição de Dados Fixos (Vindo da Planilha/AEE)
        with st.expander("🔍 Ver Dados Base do AEE (Itens 01 a 06)", expanded=False):
            st.markdown(f"""
            **Histórico:** {dados['(02) Histórico']}  
            **Necessidades:** {dados['(03) Necessidades Educacionais Específicas']}  
            **Habilidades:** {dados['(04) Conhecimentos e Habilidades']}  
            **Dificuldades:** {dados['(05) Dificuldades Apresentadas']}  
            **Adaptações Sugeridas:** {dados['(06) Adaptações Razoáveis e/ou Acessibilidades']}
            """)

        st.divider()

        # Inputs do Professor da Disciplina
        col1, col2 = st.columns(2)
        with col1:
            docente_nome = st.text_input("Nome do Docente:")
            componente = st.text_input("Componente Curricular (Matéria):")
        with col2:
            conteudo_aula = st.text_area("Conteúdo Programático específico (ex: Frações, Genética...):")

        if st.button("🚀 Gerar Proposta de Adaptação Curricular"):
            if not docente_nome or not conteudo_aula:
                st.warning("Preencha o nome do docente e o conteúdo da aula.")
            else:
                with st.spinner("A IA está analisando o perfil do aluno e sugerindo adaptações..."):
                    resultado_ia = gerar_sugestao_pei(dados, docente_nome, componente, conteudo_aula)
                    st.session_state['rascunho_pei'] = resultado_ia

        # 5. Área de Edição e Finalização
        if 'rascunho_pei' in st.session_state:
            st.subheader("📝 Revisão e Edição Final")
            st.info("O texto abaixo foi gerado pela IA. Você pode editar qualquer parte antes de exportar.")
            
            # Campo editável pelo professor
            texto_final = st.text_area("Edite o conteúdo dos itens 07 a 11:", value=st.session_state['rascunho_pei'], height=400)

            # Montagem do Documento Final formatado
            pei_completo = f"""
INSTITUTO FEDERAL DE EDUCAÇÃO, CIÊNCIA E TECNOLOGIA DE MATO GROSSO
ANEXO II - PLANO EDUCACIONAL INDIVIDUALIZADO (PEI)

(01) DADOS PESSOAIS
Estudante: {dados['Nome do Estudante']}
Responsável: {dados['Nome do Pai/Mãe ou responsável']}
Telefone: {dados['Telefone para contato']}
Nascimento: {dados['Data do Nascimento']} | Idade: {dados['Idade']}
Curso: {dados['Curso']}
Componente Curricular: {componente}
Docente: {docente_nome}

(02) HISTÓRICO
{dados['(02) Histórico']}

(03) NECESSIDADES EDUCACIONAIS ESPECÍFICAS
{dados['(03) Necessidades Educacionais Específicas']}

(04) CONHECIMENTOS E HABILIDADES | (05) DIFICULDADES
Habilidades: {dados['(04) Conhecimentos e Habilidades']}
Dificuldades: {dados['(05) Dificuldades Apresentadas']}

(06) ADAPTAÇÕES RAZOÁVEIS E/OU ACESSIBILIDADES
{dados['(06) Adaptações Razoáveis e/ou Acessibilidades']}

----------------------------------------------------------------------
ADAPTAÇÕES CURRICULARES (ITENS 07 A 11)
----------------------------------------------------------------------
{texto_final}

(14) ASSINATURAS
___________________________          ___________________________
Docente                               Coordenação de Curso

Data: {pd.Timestamp.now().strftime('%d/%m/%Y')}
            """

            st.download_button(
                label="📥 Baixar PEI Finalizado (.txt)",
                data=pei_completo,
                file_name=f"PEI_{aluno_selecionado}_{componente}.txt",
                mime="text/plain"
            )
else:
    st.warning("Nenhum dado encontrado na planilha.")

