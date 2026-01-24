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
        return "Erro ao gerar sugestão automática via IA."

# --- INTERFACE ---
st.title("🌿 Gerador de PEI Oficial - IFMT")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
except Exception as e:
    st.error(f"Erro na conexão com a planilha: {e}")
    st.stop()

# Mapeamento de Colunas conforme a planilha
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
        
        st.subheader("📝 Preenchimento do Plano")
        
        # Bloco de Identificação
        c1, c2 = st.columns(2)
        with c1:
            docente_input = st.text_input("Docente responsável:")
            materia_input = st.text_input("Componente Curricular (Matéria):")
        with c2:
            # Melhoria: Histórico Editável
            hist_original = aluno.get(COL_HIST, "")
            texto_historico = st.text_area("(02) Histórico (Edite se necessário):", value=hist_original, height=100)

        conteudo_input = st.text_area("(08) Conteúdo Programático específico para este plano:", height=100)

        if st.button("🚀 Gerar Sugestões Pedagógicas (IA)"):
            if not conteudo_input:
                st.warning("Informe o conteúdo para que a IA possa sugerir as adaptações.")
            else:
                prompt_ia = f"Gere os itens 07, 09, 10 e 11 do PEI para {aluno_nome} na matéria {materia_input}. Necessidades: {aluno[COL_NECESSIDADE]}. Tema: {conteudo_input}."
                st.session_state['rascunho_ia'] = call_maritalk(prompt_ia)

        if 'rascunho_ia' in st.session_state:
            res_ia = st.text_area("Itens (07) Objetivos, (09) Metodologia, (10) Avaliação e (11) Resultados:", value=st.session_state['rascunho_ia'], height=300)
            
            # Bibliografias
            b1, b2 = st.columns(2)
            with b1:
                bib_b = st.text_input("(12) Bibliografia Básica:", "Conforme o PPC do curso.")
            with b2:
                bib_c = st.text_input("(13) Bibliografia Complementar:", "Materiais adaptados e recursos digitais.")

            if st.button("📄 Finalizar e Gerar PDF"):
                pdf = PEI_PDF()
                pdf.add_page()
                
                # (01) DADOS PESSOAIS
                pdf.section_title("(01) DADOS PESSOAIS")
                pdf.content_body("Estudante", aluno[COL_NOME])
                pdf.content_body("Responsável", f"{aluno.get(COL_RESP, '')} | Contato: {aluno.get(COL_TEL, '')}")
                pdf.content_body("Nascimento", f"{aluno.get(COL_NASC, '')} | Idade: {aluno.get(COL_IDADE, '')}")
                pdf.content_body("Curso", aluno.get(COL_CURSO, ''))
                pdf.content_body("Docente", docente_input)
                pdf.content_body("Componente Curricular", materia_input)

                # (02) HISTÓRICO (Usa o texto editado na interface)
                pdf.section_title("(02) HISTÓRICO")
                pdf.content_body("Relato", texto_historico)
                
                # (03) a (06)
                pdf.section_title("(03) NECESSIDADES EDUCACIONAIS ESPECÍFICAS")
                pdf.content_body("Diagnóstico", aluno.get(COL_NECESSIDADE, ''))

                pdf.section_title("(04/05) HABILIDADES E DIFICULDADES")
                pdf.content_body("Habilidades", aluno.get(COL_HAB, ''))
                pdf.content_body("Dificuldades", aluno.get(COL_DIF, ''))

                pdf.section_title("(06) ADAPTAÇÕES RAZOÁVEIS")
                pdf.content_body("Recursos", aluno.get(COL_ADAPT, ''))

                # (07) a (11) - Conteúdo e IA
                pdf.section_title("DESENVOLVIMENTO PEDAGÓGICO")
                pdf.content_body("(08) Conteúdo Programático", conteudo_input)
                pdf.set_font("Arial", "", 10)
                pdf.multi_cell(0, 5, res_ia)

                # (12) a (13) - Bibliografia
                pdf.section_title("(12) BIBLIOGRAFIA BÁSICA")
                pdf.content_body("Referências", bib_b)
                pdf.section_title("(13) BIBLIOGRAFIA COMPLEMENTAR")
                pdf.content_body("Referências", bib_c)

                # (14) ASSINATURAS
                pdf.ln(10)
                pdf.section_title("(14) ASSINATURAS")
                pdf.ln(10)
                pdf.set_font("Arial", "", 8)
                pdf.cell(60, 0, "__________________________", ln=0)
                pdf.cell(60, 0, "__________________________", ln=0)
                pdf.cell(60, 0, "__________________________", ln=1)
                pdf.cell(60, 10, "Docente", ln=0)
                pdf.cell(60, 10, "Coordenação de Curso", ln=0)
                pdf.cell(60, 10, "Departamento de Ensino", ln=1)

                pdf_bytes = bytes(pdf.output()) 
                
                st.download_button(
                    label="📥 Baixar PDF Finalizado",
                    data=pdf_bytes,
                    file_name=f"PEI_{aluno_nome}.pdf",
                    mime="application/pdf"
                )
