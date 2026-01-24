import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerador PEI - IFMT", layout="wide")

# --- CLASSE PARA GERAÇÃO DO PDF (DIAGRAMAÇÃO EXATA) ---
class PEI_PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 10)
        self.cell(0, 5, "Ministério da Educação", ln=True, align="C")
        self.cell(0, 5, "Secretaria de Educação Profissional e Tecnológica", ln=True, align="C")
        self.cell(0, 5, "Instituto Federal de Educação, Ciência e Tecnologia de Mato Grosso", ln=True, align="C")
        self.ln(5)
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "ANEXO II - PLANO EDUCACIONAL INDIVIDUALIZADO (PEI)", border="B", ln=True, align="C")
        self.ln(5)

    def section_title(self, title):
        self.set_font("Arial", "B", 10)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 8, title, ln=True, fill=True)
        self.ln(2)

    def content_body(self, text):
        self.set_font("Arial", "", 10)
        self.multi_cell(0, 5, str(text))
        self.ln(4)

# --- FUNÇÃO IA (MARITALK) ---
def call_maritalk(prompt):
    try:
        api_key = st.secrets["MARITALK_API_KEY"]
        url = "https://chat.maritaca.ai/api/chat/completions"
        headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
        data = {
            "model": "sabia-3",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
            "temperature": 0.7
        }
        response = requests.post(url, headers=headers, json=data)
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Erro na IA: {e}"

# --- INTERFACE STREAMLIT ---
st.title("🌿 Gerador de PEI Oficial - IFMT")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
except Exception as e:
    st.error(f"Erro na planilha: {e}")
    st.stop()

# Mapeamento das colunas da planilha (conforme imagem enviada)
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

if COL_NOME in df.columns:
    aluno_nome = st.selectbox("Selecione o Estudante:", ["Selecione..."] + df[COL_NOME].tolist())
    
    if aluno_nome != "Selecione...":
        aluno = df[df[COL_NOME] == aluno_nome].iloc[0].to_dict()
        
        st.subheader("📝 Dados da Disciplina")
        c1, c2 = st.columns(2)
        with c1:
            docente = st.text_input("Docente [Item 13]:")
            componente = st.text_input("Componente Curricular [Item 12]:")
        with c2:
            tema = st.text_area("Conteúdo Programático [Item 08]:")

        if st.button("🚀 Gerar Planejamento (Itens 07 a 11)"):
            prompt = f"Gere os itens 07, 09, 10 e 11 do PEI para {aluno_nome}. Necessidade: {aluno[COL_NECESSIDADE]}. Matéria: {componente}. Tema: {tema}."
            with st.spinner("IA redigindo proposta pedagógica..."):
                st.session_state['rascunho_ia'] = call_maritalk(prompt)

        if 'rascunho_ia' in st.session_state:
            st.divider()
            # Campos Editáveis para os 14 itens
            st.subheader("🔍 Revisão Final dos 14 Itens")
            
            it7_11 = st.text_area("Itens (07) a (11) - Gerados pela IA:", value=st.session_state['rascunho_ia'], height=300)
            bib_basica = st.text_area("(12) Bibliografia Básica:", "Ex: Livro texto da disciplina...")
            bib_compl = st.text_area("(13) Bibliografia Complementar:", "Ex: Artigos, sites, vídeos...")

            if st.button("📄 Gerar PDF de Alta Qualidade"):
                pdf = PEI_PDF()
                pdf.add_page()
                
                # (01) DADOS PESSOAIS [cite: 5, 6, 7]
                pdf.section_title("(01) DADOS PESSOAIS")
                pdf.content_body(f"Nome do Estudante: {aluno[COL_NOME]}\n"
                                 f"Responsável: {aluno.get(COL_RESPONSAVEL, '')} | Contato: {aluno.get(COL_CONTATO, '')}\n"
                                 f"Nascimento: {aluno.get(COL_NASC, '')} | Idade: {aluno.get(COL_IDADE, '')}\n"
                                 f"Curso: {aluno.get(COL_CURSO, '')}\n"
                                 f"Componente Curricular: {componente}\n"
                                 f"Docente: {docente}")

                # (02) a (06) [cite: 14, 15, 16, 18]
                pdf.section_title("(02) HISTÓRICO")
                pdf.content_body(aluno.get(COL_HIST, ''))
                
                pdf.section_title("(03) NECESSIDADES EDUCACIONAIS ESPECÍFICAS")
                pdf.content_body(aluno.get(COL_NECESSIDADE, ''))
                
                pdf.section_title("(04/05) HABILIDADES E DIFICULDADES")
                pdf.content_body(f"Habilidades: {aluno.get(COL_HABILIDADE, '')}\n"
                                 f"Dificuldades: {aluno.get(COL_DIFICULDADE, '')}")
                
                pdf.section_title("(06) ADAPTAÇÕES RAZOÁVEIS")
                pdf.content_body(aluno.get(COL_ADAPTACAO, ''))

                # (07) a (11) [cite: 19, 20, 21, 22, 24]
                pdf.section_title("PLANEJAMENTO PEDAGÓGICO (07 A 11)")
                pdf.content_body(it7_11)

                # (12) a (13) [cite: 25, 26]
                pdf.section_title("(12) BIBLIOGRAFIA BÁSICA")
                pdf.content_body(bib_basica)
                pdf.section_title("(13) BIBLIOGRAFIA COMPLEMENTAR")
                pdf.content_body(bib_compl)

                # (14) ASSINATURAS [cite: 27]
                pdf.ln(10)
                pdf.section_title("(14) ASSINATURAS")
                pdf.ln(10)
                pdf.set_font("Arial", "", 8)
                col_w = 60
                pdf.cell(col_w, 0, "__________________________", ln=0)
                pdf.cell(col_w, 0, "__________________________", ln=0)
                pdf.cell(col_w, 0, "__________________________", ln=1)
                pdf.cell(col_w, 10, "Docente", ln=0)
                pdf.cell(col_w, 10, "Coordenação de Curso", ln=0)
                pdf.cell(col_w, 10, "Departamento de Ensino", ln=1)

                pdf_output = pdf.output()
                st.download_button(label="📥 Baixar PEI em PDF", data=pdf_output, 
                                   file_name=f"PEI_{aluno_nome}.pdf", mime="application/pdf")
