import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerador PEI - IFMT", layout="wide")

# --- CLASSE PARA GERAÇÃO DO PDF (LAYOUT ANEXO II) ---
class PEI_PDF(FPDF):
    def header(self):
        # Cabeçalho oficial [cite: 1, 2]
        self.set_font("Arial", "B", 10)
        self.cell(0, 5, "Ministério da Educação", ln=True, align="C") [cite: 1]
        self.cell(0, 5, "Secretaria de Educação Profissional e Tecnológica", ln=True, align="C") [cite: 2]
        self.cell(0, 5, "Instituto Federal de Educação, Ciência e Tecnologia de Mato Grosso", ln=True, align="C") [cite: 2]
        self.ln(5)
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "ANEXO II - PLANO EDUCACIONAL INDIVIDUALIZADO (PEI)", border="B", ln=True, align="C") [cite: 3, 4]
        self.ln(5)

    def section_title(self, title):
        self.set_font("Arial", "B", 10)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 8, title, ln=True, fill=True)
        self.ln(2)

    def content_body(self, label, text):
        self.set_font("Arial", "B", 10)
        self.write(5, f"{label}: ")
        self.set_font("Arial", "", 10)
        self.multi_cell(0, 5, str(text))
        self.ln(2)

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
    except Exception:
        return "Erro ao gerar sugestão automática."

# --- INTERFACE ---
st.title("🌿 Gerador de PEI Oficial - IFMT")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
except Exception as e:
    st.error(f"Erro na planilha: {e}")
    st.stop()

# Mapeamento de Colunas (Planilha)
COL_NOME = 'Nome do Estudante'
COL_RESP = 'Nome do Pai/Mãe ou responsável'
COL_TEL = 'Telefone para contato'
COL_NASC = 'Data do Nascimento'
COL_IDADE = 'Idade'
COL_CURSO = 'Curso'
COL_HIST = '(02) Histórico'
COL_NECESSIDADE = '(03) Necessidades Educacionais Específicas'
COL_HAB = '(04) Conhecimentos e Habilidades'
COL_DIF = '(05) Dificuldades Apresentadas'
COL_ADAPT = '(06) Adaptações Razoáveis e/ou Acessibilidades'

if COL_NOME in df.columns:
    aluno_nome = st.selectbox("Selecione o Estudante:", ["Selecione..."] + df[COL_NOME].tolist())
    
    if aluno_nome != "Selecione...":
        aluno = df[df[COL_NOME] == aluno_nome].iloc[0].to_dict()
        
        # Inputs Complementares (Itens 12 e 13) [cite: 12, 13]
        st.subheader("📝 Dados do Componente Curricular")
        c1, c2 = st.columns(2)
        with c1:
            docente = st.text_input("Docente:") [cite: 13]
            componente = st.text_input("Componente Curricular:") [cite: 12]
        with c2:
            conteudo = st.text_area("Conteúdo Programático [Item 08]:") [cite: 20]

        if st.button("🚀 Gerar Proposta Pedagógica (IA)"):
            prompt = f"Gere os itens 07, 09, 10 e 11 do PEI para {aluno_nome} em {componente}. Necessidades: {aluno[COL_NECESSIDADE]}."
            st.session_state['rascunho'] = call_maritalk(prompt)

        if 'rascunho' in st.session_state:
            res_ia = st.text_area("Revise os Itens (07) a (11):", value=st.session_state['rascunho'], height=250)
            bib_b = st.text_input("(12) Bibliografia Básica:", "Conforme PPC do curso.") [cite: 25]
            bib_c = st.text_input("(13) Bibliografia Complementar:", "Materiais adaptados e vídeos.") [cite: 26]

            if st.button("📄 Gerar e Baixar PDF"):
                pdf = PEI_PDF()
                pdf.add_page()
                
                # (01) DADOS PESSOAIS [cite: 5-13]
                pdf.section_title("(01) DADOS PESSOAIS")
                pdf.content_body("Nome do Estudante", aluno[COL_NOME]) [cite: 6]
                pdf.content_body("Responsável", f"{aluno.get(COL_RESP, '')} | Contato: {aluno.get(COL_TEL, '')}") [cite: 7]
                pdf.content_body("Nascimento", f"{aluno.get(COL_NASC, '')} | Idade: {aluno.get(COL_IDADE, '')}") [cite: 9, 10]
                pdf.content_body("Curso", aluno.get(COL_CURSO, '')) [cite: 11]
                pdf.content_body("Docente", docente) [cite: 13]
                pdf.content_body("Componente Curricular", componente) [cite: 12]

                # (02) a (06) [cite: 14-18]
                pdf.section_title("(02) HISTÓRICO") [cite: 14]
                pdf.content_body("Relato", aluno.get(COL_HIST, ''))
                
                pdf.section_title("(03) NECESSIDADES EDUCACIONAIS ESPECÍFICAS") [cite: 15]
                pdf.content_body("Diagnóstico", aluno.get(COL_NECESSIDADE, ''))

                pdf.section_title("(04/05) HABILIDADES E DIFICULDADES") [cite: 16]
                pdf.content_body("Habilidades", aluno.get(COL_HAB, ''))
                pdf.content_body("Dificuldades", aluno.get(COL_DIF, ''))

                pdf.section_title("(06) ADAPTAÇÕES RAZOÁVEIS") [cite: 18]
                pdf.content_body("Recursos", aluno.get(COL_ADAPT, ''))

                # (07) a (13) [cite: 19-26]
                pdf.section_title("PLANEJAMENTO PEDAGÓGICO")
                pdf.content_body("Conteúdo Programático (08)", conteudo) [cite: 20]
                pdf.multi_cell(0, 5, res_ia) # Itens 07, 09, 10, 11 [cite: 19, 21, 22, 24]
                pdf.content_body("(12) Bibliografia Básica", bib_b) [cite: 25]
                pdf.content_body("(13) Bibliografia Complementar", bib_c) [cite: 26]

                # (14) ASSINATURAS [cite: 27-29]
                pdf.ln(10)
                pdf.section_title("(14) ASSINATURAS")
                pdf.ln(10)
                pdf.set_font("Arial", "", 8)
                pdf.cell(60, 0, "__________________________", ln=0)
                pdf.cell(60, 0, "__________________________", ln=0)
                pdf.cell(60, 0, "__________________________", ln=1)
                pdf.cell(60, 10, "Docente", ln=0) [cite: 23]
                pdf.cell(60, 10, "Coordenação de Curso", ln=0) [cite: 28]
                pdf.cell(60, 10, "Departamento de Ensino", ln=1) [cite: 29]

                # --- CORREÇÃO DO ERRO AQUI ---
                # Geramos os bytes do PDF explicitamente
                pdf_bytes = bytes(pdf.output()) 
                
                st.download_button(
                    label="📥 Clique para Baixar o PDF",
                    data=pdf_bytes,
                    file_name=f"PEI_{aluno_nome}.pdf",
                    mime="application/pdf"
                )
