import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests

# 1. Configurações da Página
st.set_page_config(page_title="Sistema PEI - IFMT", layout="wide")

# Estilização IFMT (Verde e Vermelho)
st.markdown("""
    <style>
    .stButton>button { background-color: #2f9e41; color: white; font-weight: bold; width: 100%; border-radius: 8px;}
    h1 { color: #2f9e41; border-bottom: 3px solid #ed1c24; }
    .aluno-card { background-color: #ffffff; padding: 25px; border-radius: 12px; border-left: 8px solid #2f9e41; box-shadow: 3px 3px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
    .label-pei { color: #2f9e41; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 2. Função REAL para chamar a IA (Maritalk)
def chamar_ia_maritalk(prompt):
    try:
        api_key = st.secrets["MARITALK_API_KEY"]
        url = "https://chat.maritaca.ai/api/chat/completions"
        headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
        data = {
            "model": "sabia-3",
            "messages": [
                {"role": "system", "content": "Você é um especialista em educação inclusiva do IFMT. Ajude professores a criarem PEIs adaptados conforme o Anexo II."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 2000,
            "temperature": 0.7
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"Erro na API ({response.status_code}): {response.text}"
    except Exception as e:
        return f"Erro de conexão: {e}"

# 3. Conexão e Carregamento (Sem cache para garantir dados novos)
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0) 
    df.columns = [str(c).strip() for c in df.columns]
except Exception as e:
    st.error(f"Erro ao carregar planilha: {e}")
    st.stop()

# Mapeamento das Colunas conforme sua planilha
COL_NOME = 'Nome do Estudante'
COL_RESPONSAVEL = 'Nome do Pai/Mãe ou responsável'
COL_CONTATO = 'Telefone para contato'
COL_NASC = 'Data do Nascimento'
COL_IDADE = 'Idade'
COL_CURSO = 'Curso'
COL_HIST = '(02) Histórico'
COL_NECESSIDADE = '(03) Necessidades Educacionais Específicas'
COL_HABILIDADE = '(04) Conhecimentos e Habilidades'
COL_DIFICULDADE = '(05) Dificuldades Apresentadas'
COL_ADAPTACAO = '(06) Adaptações Razoáveis e/ou Acessibilidades'

# 4. Interface Principal
st.title("🌿 Sistema PEI - IFMT")

if COL_NOME not in df.columns:
    st.error(f"⚠️ A coluna '{COL_NOME}' não foi detectada. Verifique os nomes no Google Sheets.")
    st.stop()

aluno_selecionado = st.selectbox("Selecione o Aluno:", ["Selecione..."] + df[COL_NOME].tolist())

if aluno_selecionado != "Selecione...":
    dados = df[df[COL_NOME] == aluno_selecionado].iloc[0].to_dict()

    # --- Exibição Completa da Ficha Técnica (Itens 01 a 06) ---
    with st.container():
        st.markdown(f"""
        <div class="aluno-card">
            <h3>(01) Dados Pessoais e Base do AEE</h3>
            <p><span class="label-pei">Estudante:</span> {dados[COL_NOME]}</p>
            <p><span class="label-pei">Curso:</span> {dados.get(COL_CURSO, 'N/A')} | <span class="label-pei">Idade:</span> {dados.get(COL_IDADE, 'N/A')}</p>
            <p><span class="label-pei">Responsável:</span> {dados.get(COL_RESPONSAVEL, 'N/A')} | <span class="label-pei">Contato:</span> {dados.get(COL_CONTATO, 'N/A')}</p>
            <hr>
            <p><span class="label-pei">(02) Histórico:</span> {dados.get(COL_HIST, 'N/A')}</p>
            <p><span class="label-pei">(03) Necessidades:</span> {dados.get(COL_NECESSIDADE, 'N/A')}</p>
            <p><span class="label-pei">(04) Habilidades:</span> {dados.get(COL_HABILIDADE, 'N/A')}</p>
            <p><span class="label-pei">(05) Dificuldades:</span> {dados.get(COL_DIFICULDADE, 'N/A')}</p>
            <p><span class="label-pei">(06) Adaptações Base:</span> {dados.get(COL_ADAPTACAO, 'N/A')}</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    
    # Entradas do Professor da Disciplina
    col1, col2 = st.columns(2)
    with col1:
        docente = st.text_input("Seu Nome (Docente):")
        materia = st.text_input("Componente Curricular (Matéria):")
    with col2:
        tema = st.text_area("Conteúdo/Tópico a ser ensinado:")

    # 5. Lógica de Geração com IA
    if st.button("🚀 Gerar Planejamento Adaptativo (IA)"):
        if not tema or not materia:
            st.warning("Por favor, preencha a matéria e o conteúdo da aula.")
        else:
            # Criando o prompt detalhado para a IA
            prompt_ia = f"""
            Com base no perfil do aluno abaixo do IFMT, gere os itens (07) ao (11) do PEI para a disciplina de {materia}.
            
            DADOS DO ALUNO:
            - Necessidades: {dados.get(COL_NECESSIDADE, 'N/A')}
            - Habilidades: {dados.get(COL_HABILIDADE, 'N/A')}
            - Dificuldades: {dados.get(COL_DIFICULDADE, 'N/A')}
            - Adaptações já existentes: {dados.get(COL_ADAPTACAO, 'N/A')}
            
            CONTEÚDO DA AULA: {tema}
            
            FORMATO DE RESPOSTA:
            Forneça sugestões práticas e pedagógicas para os seguintes tópicos do Anexo II:
            (07) OBJETIVOS ESPECÍFICOS
            (08) CONTEÚDOS PROGRAMÁTICOS ADAPTADOS
            (09) METODOLOGIA (como ensinar este aluno especificamente)
            (10) AVALIAÇÃO (como medir o aprendizado dele neste tema)
            (11) RESULTADOS ESPERADOS
            """
            
            with st.spinner("A IA está analisando o perfil e criando o plano pedagógico..."):
                resultado_ia = chamar_ia_maritalk(prompt_ia)
                st.session_state['rascunho'] = resultado_ia

    # 6. Edição e Download
    if 'rascunho' in st.session_state:
        st.subheader("📝 Revisão e Edição Final")
        st.caption("O professor deve revisar o conteúdo gerado pela IA antes de imprimir.")
        
        texto_editavel = st.text_area("Edite os itens gerados:", value=st.session_state['rascunho'], height=400)
        
        # Montagem do arquivo para download formatado
        documento_download = f"""
MINISTÉRIO DA EDUCAÇÃO - IFMT
ANEXO II - PLANO EDUCACIONAL INDIVIDUALIZADO (PEI)

(01) DADOS PESSOAIS
Estudante: {dados[COL_NOME]}
Curso: {dados.get(COL_CURSO, 'N/A')}
Docente: {docente}
Matéria: {materia}

(03) NECESSIDADES ESPECÍFICAS: {dados.get(COL_NECESSIDADE, 'N/A')}
(06) ADAPTAÇÕES RAZOÁVEIS: {dados.get(COL_ADAPTACAO, 'N/A')}

-----------------------------------------------------------
PLANEJAMENTO (ITENS 07 A 11)
-----------------------------------------------------------
{texto_editavel}

Data: {pd.Timestamp.now().strftime('%d/%m/%Y')}
Assinatura: _________________________________________
        """
        
        st.download_button(
            label="📥 Baixar PEI Finalizado", 
            data=documento_download, 
            file_name=f"PEI_{aluno_selecionado}.txt",
            mime="text/plain"
        )
