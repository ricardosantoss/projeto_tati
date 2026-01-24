import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests

# Configurações de Página
st.set_page_config(page_title="Sistema PEI - IFMT", layout="wide")

# Estilização IFMT
st.markdown("""
    <style>
    .main { background-color: #f5f5f5; }
    .stButton>button { background-color: #2f9e41; color: white; width: 100%; }
    h1 { color: #2f9e41; border-bottom: 2px solid #ed1c24; }
    .preview-box { background-color: white; padding: 20px; border: 1px solid #ccc; border-radius: 5px; font-family: 'Courier New', Courier, monospace; }
    </style>
    """, unsafe_allow_html=True)

def call_maritalk(prompt):
    try:
        api_key = st.secrets["MARITALK_API_KEY"]
        url = "https://chat.maritaca.ai/api/chat/completions"
        headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
        data = {
            "model": "sabia-3",
            "messages": [
                {"role": "system", "content": "Você é um especialista em educação inclusiva do IFMT. Responda em formato JSON com as chaves: objetivos, conteudos, metodologia, avaliacao, resultados, bibliografia."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        response = requests.post(url, headers=headers, json=data)
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return None

# Conexão
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read()

st.title("🌿 Elaboração de PEI Adaptado - IFMT")

if 'Nome' in df.columns:
    aluno_nome = st.selectbox("Selecione o Aluno:", ["Selecione..."] + df['Nome'].tolist())
    
    if aluno_nome != "Selecione...":
        aluno = df[df['Nome'] == aluno_nome].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Dados do AEE (Base)")
            st.info(f"**Necessidades:** {aluno['Necessidades']}")
            st.info(f"**Habilidades:** {aluno['Habilidades']}")
        
        with col2:
            st.subheader("Dados da Disciplina")
            docente = st.text_input("Nome do Docente:", placeholder="Nome do professor da disciplina")
            componente = st.text_input("Componente Curricular:", placeholder="Ex: Matemática I")
            tema = st.text_area("Conteúdo a ser adaptado:", placeholder="Descreva o que será ensinado...")

        if st.button("1. Gerar Proposta Inicial com IA"):
            prompt = f"Gere adaptações para o aluno {aluno_nome} que tem {aluno['Necessidades']}. Conteúdo: {tema}. Foque nos itens 7 a 12 do PEI."
            with st.spinner("IA trabalhando na adaptação..."):
                # Simulação de resposta ou chamada real
                resposta_ia = call_maritalk(prompt)
                # Nota: Idealmente aqui você faria o parse do JSON da IA para preencher os campos abaixo
                st.session_state['proposta'] = True

        if 'proposta' in st.session_state:
            st.divider()
            st.subheader("2. Revisão e Edição (Itens 07 a 12)")
            st.warning("Abaixo você pode editar os campos gerados pela IA antes de finalizar o documento.")
            
            # Campos Editáveis
            obj = st.text_area("(07) Objetivos Espetíficos", "Defina o que o aluno deve alcançar...")
            cont = st.text_area("(08) Conteúdos Programáticos", tema)
            metodo = st.text_area("(09) Metodologia", "Descreva como você vai ensinar (ex: uso de material concreto, tempo estendido)...")
            avalia = st.text_area("(10) Avaliação", "Como o aluno será avaliado?")
            resul = st.text_area("(11) Resultados Esperados", "O que se espera que o aluno aprenda ao final?")
            biblio = st.text_area("(12/13) Bibliografia", "Indique os materiais de apoio.")

            # Montagem do Documento Final (Formatação similar ao Anexo II)
            pei_final = f"""
            MINISTÉRIO DA EDUCAÇÃO
            SECRETARIA DE EDUCAÇÃO PROFISSIONAL E TECNOLÓGICA
            INSTITUTO FEDERAL DE MATO GROSSO
            
            ANEXO II - PLANO EDUCACIONAL INDIVIDUALIZADO (PEI)
            
            (01) DADOS PESSOAIS
            Nome: {aluno['Nome']}
            Responsável: {aluno['Responsavel']} | Contato: {aluno['Telefone']}
            Nascimento: {aluno['Nascimento']}
            Curso: {aluno['Curso']}
            Componente Curricular: {componente}
            Docente: {docente}
            
            (02) HISTÓRICO
            {aluno['Historico']}
            
            (03) NECESSIDADES EDUCACIONAIS ESPECÍFICAS
            {aluno['Necessidades']}
            
            (04) CONHECIMENTOS/HABILIDADES | (05) DIFICULDADES
            Habilidades: {aluno['Habilidades']}
            Dificuldades: {aluno['Dificuldades']}
            
            (06) ADAPTAÇÕES RAZOÁVEIS (BASE)
            {aluno['Adaptacoes_Base']}
            
            -----------------------------------------------------------
            ADAPTAÇÕES ESPECÍFICAS PARA O CONTEÚDO
            -----------------------------------------------------------
            
            (07) OBJETIVOS ESPECÍFICOS
            {obj}
            
            (08) CONTEÚDOS PROGRAMÁTICOS
            {cont}
            
            (09) METODOLOGIA
            {metodo}
            
            (10) AVALIAÇÃO
            {avalia}
            
            (11) RESULTADOS ESPERADOS
            {resul}
            
            (12/13) BIBLIOGRAFIA
            {biblio}
            
            (14) ASSINATURAS
            Docente: ___________________________ 
            Coordenação: _______________________ Data: ___/___/___
            """
            
            st.subheader("3. Visualização e Download")
            st.code(pei_final, language="text")
            
            st.download_button(
                label="📥 Baixar PEI Finalizado (.txt)",
                data=pei_final,
                file_name=f"PEI_{aluno_nome}_{componente}.txt",
                mime="text/plain"
            )


