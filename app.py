import os
import io
import re
import tempfile
import requests
import pandas as pd
import streamlit as st
from fpdf import FPDF
from streamlit_gsheets import GSheetsConnection

# =========================================================
# CONFIG STREAMLIT
# =========================================================
st.set_page_config(page_title="Organizador do PEI - IFMT", layout="wide")

# CSS para melhorar a estética dos text_areas
st.markdown("""
    <style>
    .stTextArea textarea { font-size: 14px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌿 Gerador de PEI Oficial - IFMT")

# =========================================================
# HELPERS
# =========================================================
def s(value) -> str:
    """String segura para evitar NaNs no PDF."""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()

def call_maritalk(prompt: str) -> str:
    try:
        api_key = st.secrets["MARITALK_API_KEY"]
        url = "https://chat.maritaca.ai/api/chat/completions"
        headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "sabia-3",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
            "temperature": 0.4,
        }
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Erro na API: {e}"

def parse_ia_blocks(text: str) -> dict:
    """Extrai blocos usando regex mais flexível."""
    out = {"07": "", "09": "", "10": "", "11": ""}
    if not text: return out
    
    # Procura por (07), 07), 07 -, **07** etc.
    patterns = {
        "07": r"(?i)(?:\(?0?7\)?|0?7\s*[-:])\s*(.*?)(?=\(?0?9\)?|0?9\s*[-:]|$)",
        "09": r"(?i)(?:\(?0?9\)?|0?9\s*[-:])\s*(.*?)(?=\(?10\)?|10\s*[-:]|$)",
        "10": r"(?i)(?:\(?10\)?|10\s*[-:])\s*(.*?)(?=\(?11\)?|11\s*[-:]|$)",
        "11": r"(?i)(?:\(?11\)?|11\s*[-:])\s*(.*?)(?=$)"
    }
    
    for tag, p in patterns.items():
        match = re.search(p, text, re.DOTALL)
        if match:
            out[tag] = match.group(1).strip()
    return out

# =========================================================
# GESTÃO DE ESTADO (CRUCIAL PARA O PREENCHIMENTO)
# =========================================================
if "applied_ok" not in st.session_state:
    st.session_state.applied_ok = False

# Inicializa campos se não existirem
keys_to_init = ["k_07", "k_08", "k_09", "k_10", "k_11", "ia_raw"]
for k in keys_to_init:
    if k not in st.session_state:
        st.session_state[k] = ""

def apply_suggestions():
    blocks = parse_ia_blocks(st.session_state.ia_raw)
    if any(blocks.values()):
        st.session_state.k_07 = blocks["07"]
        st.session_state.k_09 = blocks["09"]
        st.session_state.k_10 = blocks["10"]
        st.session_state.k_11 = blocks["11"]
        st.session_state.applied_ok = True

# =========================================================
# PDF (Ajustes de Layout e Fontes)
# =========================================================
class PEI_PDF(FPDF):
    def __init__(self, logo_path=None):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=15)
        self.logo_path = logo_path
        
    def header(self):
        if self.logo_path and os.path.exists(self.logo_path):
            self.image(self.logo_path, x=92, y=8, w=25)
            self.ln(15)
        
        self.set_font("Arial", "B", 10)
        self.cell(0, 5, "Ministério da Educação", ln=True, align="C")
        self.cell(0, 5, "Secretaria de Educação Profissional e Tecnológica", ln=True, align="C")
        self.cell(0, 5, "Instituto Federal de Mato Grosso", ln=True, align="C")
        self.ln(5)
        self.set_font("Arial", "B", 12)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 8, "ANEXO II - PLANO EDUCACIONAL INDIVIDUALIZADO (PEI)", ln=True, align="C", border=1, fill=True)
        self.ln(4)

    def section_title(self, txt):
        self.set_font("Arial", "B", 9)
        self.set_fill_color(245, 245, 245)
        self.cell(0, 6, txt, ln=True, border=1, fill=True)

    def draw_box(self, label, content, min_h=15):
        self.section_title(label)
        self.set_font("Arial", "", 9)
        # Multi_cell calcula altura automaticamente
        self.multi_cell(0, 5, s(content), border=1, align="L")
        self.ln(2)

# =========================================================
# CARREGAMENTO DE DADOS
# =========================================================
@st.cache_data(ttl=600)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    return conn.read()

try:
    df = load_data()
    df.columns = [str(c).strip() for c in df.columns]
except Exception as e:
    st.error(f"Erro na planilha: {e}")
    st.stop()

# =========================================================
# UI - INTERFACE
# =========================================================
aluno_nome = st.selectbox("Selecione o Estudante:", ["Selecione..."] + df["Nome do Estudante"].unique().tolist())

if aluno_nome != "Selecione...":
    aluno = df[df["Nome do Estudante"] == aluno_nome].iloc[0].to_dict()
    
    with st.expander("📌 Dados de Identificação", expanded=True):
        c1, c2 = st.columns(2)
        docente = c1.text_input("Docente Responsável:", placeholder="Nome do professor")
        materia = c2.text_input("Componente Curricular:", placeholder="Ex: Matemática I")
        
        c3, c4, c5 = st.columns([2, 1, 1])
        curso = c3.text_input("Curso:", value=s(aluno.get("Curso")))
        contato = c4.text_input("Contato:", value=s(aluno.get("Telefone para contato")))
        nasc = c5.text_input("Data Nasc.:", value=s(aluno.get("Data do Nascimento")))

    # Histórico e Necessidades
    texto_hist = st.text_area("(02) Histórico do Estudante:", value=s(aluno.get("(02) Histórico")), height=100)
    
    col_a, col_b = st.columns(2)
    nec_val = col_a.text_area("(03) Necessidades Específicas:", value=s(aluno.get("(03) Necessidades Educacionais Específicas")), height=100)
    hab_val = col_b.text_area("(04) Conhecimentos/Habilidades:", value=s(aluno.get("(04) Conhecimentos e Habilidades")), height=100)

    # Parte Pedagógica
    st.markdown("---")
    st.subheader("🎯 Planejamento Pedagógico")
    
    st.text_area("(08) Conteúdos Programáticos (Base para IA):", key="k_08", height=80)
    
    # Bloco de IA
    col_ia1, col_ia2 = st.columns([1, 4])
    with col_ia1:
        if st.button("🚀 Gerar com IA"):
            if not materia or not st.session_state.k_08:
                st.warning("Preencha a Matéria e o Conteúdo (08).")
            else:
                with st.spinner("Sabia-3 pensando..."):
                    prompt = f"Gere um PEI para {aluno_nome} na matéria {materia}. Conteúdo: {st.session_state.k_08}. Necessidades: {nec_val}. Responda estritamente nos blocos (07), (09), (10) e (11)."
                    st.session_state.ia_raw = call_maritalk(prompt)

    if st.session_state.ia_raw:
        with st.container(border=True):
            st.markdown("**Sugestão da IA recebida!**")
            if st.button("✅ Aplicar nos campos abaixo"):
                apply_suggestions()
                st.rerun()
            st.info(st.session_state.ia_raw[:200] + "...")

    # Campos Editáveis
    c_left, c_right = st.columns(2)
    with c_left:
        st.text_area("(07) Objetivos Específicos:", key="k_07", height=150)
        st.text_area("(09) Metodologia:", key="k_09", height=150)
    with c_right:
        st.text_area("(10) Avaliação:", key="k_10", height=150)
        st.text_area("(11) Resultados Esperados:", key="k_11", height=150)

    # PDF
    if st.button("📦 Gerar PDF Final"):
        pdf = PEI_PDF()
        pdf.add_page()
        
        # Grid de Identificação
        pdf.section_title("(01) DADOS PESSOAIS")
        pdf.set_font("Arial", "", 9)
        pdf.cell(0, 7, f"Estudante: {aluno_nome} | Curso: {curso}", ln=True, border=1)
        pdf.cell(0, 7, f"Docente: {docente} | Disciplina: {materia}", ln=True, border=1)
        
        # Seções de texto
        pdf.draw_box("(02) HISTÓRICO", texto_hist)
        pdf.draw_box("(03) NECESSIDADES", nec_val)
        pdf.draw_box("(04) HABILIDADES", hab_val)
        pdf.draw_box("(07) OBJETIVOS ESPECÍFICOS", st.session_state.k_07)
        pdf.draw_box("(08) CONTEÚDOS", st.session_state.k_08)
        pdf.draw_box("(09) METODOLOGIA", st.session_state.k_09)
        pdf.draw_box("(10) AVALIAÇÃO", st.session_state.k_10)
        pdf.draw_box("(11) RESULTADOS ESPERADOS", st.session_state.k_11)

        # Assinaturas simplificadas para caber
        pdf.ln(10)
        pdf.set_font("Arial", "", 8)
        pdf.cell(60, 5, "__________________________", ln=0, align="C")
        pdf.cell(60, 5, "__________________________", ln=0, align="C")
        pdf.cell(60, 5, "__________________________", ln=1, align="C")
        pdf.cell(60, 5, "Docente", ln=0, align="C")
        pdf.cell(60, 5, "Coordenação", ln=0, align="C")
        pdf.cell(60, 5, "Núcleo de Apoio", ln=1, align="C")

        # Output
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf.output(tmp.name)
            with open(tmp.name, "rb") as f:
                st.download_button("📥 Baixar PEI em PDF", f, file_name=f"PEI_{aluno_nome}.pdf")
