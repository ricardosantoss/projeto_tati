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
# CONFIG E ESTADO
# =========================================================
st.set_page_config(page_title="Gerador PEI - IFMT", layout="wide")


def init_session_keys():
    keys = ["k_07", "k_08", "k_09", "k_10", "k_11", "ia_raw"]
    for k in keys:
        if k not in st.session_state:
            st.session_state[k] = ""


init_session_keys()

# =========================================================
# SANITIZAÇÃO DE TEXTO PARA PDF (sem fontes externas)
# =========================================================
def safe_pdf_text(s: str) -> str:
    """
    Normaliza caracteres comuns que quebram o FPDF com core fonts,
    e garante que a string final é codificável em cp1252.
    """
    if s is None:
        return ""
    s = str(s)

    replacements = {
        "\u2013": "-",   # – en dash
        "\u2014": "-",   # — em dash
        "\u2212": "-",   # − minus
        "\u2018": "'", "\u2019": "'",  # ‘ ’
        "\u201C": '"', "\u201D": '"',  # “ ”
        "\u2022": "*",   # • bullet
        "\u00A0": " ",   # non-breaking space
        "\u2026": "...", # …
        "\t": " ",
    }
    for a, b in replacements.items():
        s = s.replace(a, b)

    s = s.replace("\r\n", "\n").replace("\r", "\n")

    # garante compatibilidade com cp1252
    try:
        s = s.encode("cp1252", errors="replace").decode("cp1252")
    except Exception:
        # fallback extremo
        s = s.encode("latin-1", errors="replace").decode("latin-1")

    return s


# =========================================================
# LÓGICA DE IA (SABIA-3)
# =========================================================
def call_maritalk(prompt: str) -> str:
    try:
        api_key = st.secrets["MARITALK_API_KEY"]
        url = "https://chat.maritaca.ai/api/chat/completions"
        headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "sabia-3",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1800,
            "temperature": 0.5,
        }
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Erro na API: {e}"


def parse_and_apply_ia(text: str):
    """Extrai os blocos e já injeta no session_state."""
    patterns = {
        "k_07": r"(?i)(?:\(?0?7\)?|0?7\s*[-:])\s*(.*?)(?=\(?0?9\)?|0?9\s*[-:]|$)",
        "k_09": r"(?i)(?:\(?0?9\)?|0?9\s*[-:])\s*(.*?)(?=\(?10\)?|10\s*[-:]|$)",
        "k_10": r"(?i)(?:\(?10\)?|10\s*[-:])\s*(.*?)(?=\(?11\)?|11\s*[-:]|$)",
        "k_11": r"(?i)(?:\(?11\)?|11\s*[-:])\s*(.*?)(?=$)",
    }
    for key, p in patterns.items():
        match = re.search(p, text, re.DOTALL)
        if match:
            st.session_state[key] = match.group(1).strip()


# =========================================================
# PDF PADRÃO ANEXO II (compatível fpdf2 e fpdf antigo)
# =========================================================
class PEI_PDF(FPDF):
    def __init__(self, *args, **kwargs):
        """
        Tenta usar core_fonts_encoding=cp1252 (fpdf2).
        Se estiver rodando com fpdf antigo, cai no fallback sem esse argumento.
        """
        try:
            super().__init__(*args, core_fonts_encoding="cp1252", **kwargs)
        except TypeError:
            super().__init__(*args, **kwargs)

        self.set_auto_page_break(auto=True, margin=12)

    def header(self):
        self.set_font("Arial", "B", 10)
        self.cell(0, 5, safe_pdf_text("Ministério da Educação"), ln=True, align="C")
        self.cell(0, 5, safe_pdf_text("Secretaria de Educação Profissional e Tecnológica"), ln=True, align="C")
        self.cell(0, 5, safe_pdf_text("Instituto Federal de Educação, Ciência e Tecnologia de Mato Grosso"), ln=True, align="C")
        self.ln(5)

        self.set_font("Arial", "B", 12)
        self.cell(0, 7, safe_pdf_text("ANEXO II"), ln=True, align="C")
        self.cell(0, 7, safe_pdf_text("PLANO EDUCACIONAL INDIVIDUALIZADO (PEI)"), ln=True, align="C")
        self.ln(5)

    def section_header(self, title):
        self.set_font("Arial", "B", 10)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 8, safe_pdf_text(f" {title}"), border=1, ln=True, fill=True)

    def info_box(self, content, min_h=10):
        self.set_font("Arial", "", 10)
        text = safe_pdf_text(content)
        self.multi_cell(0, 6, text, border=1, align="L")
        self.ln(1)


# =========================================================
# INTERFACE STREAMLIT
# =========================================================
col_esq, col_centro, col_dir = st.columns([2, 3, 2])

with col_centro:
    st.image("ifmt_barra.png", width=80)
    st.markdown(
        "<h3 style='text-align: center;'>Gerador de PEI - IFMT</h3>",
        unsafe_allow_html=True
    )

# Carregamento de dados simplificado
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read()
df.columns = [str(c).strip() for c in df.columns]

# Evita erro se a coluna tiver NaN
nomes = df["Nome do Estudante"].dropna().unique().tolist()

aluno_nome = st.selectbox(
    "Selecione o Estudante:",
    ["Selecione..."] + nomes,
)

if aluno_nome != "Selecione...":
    aluno = df[df["Nome do Estudante"] == aluno_nome].iloc[0].to_dict()

    # (01) DADOS PESSOAIS
    with st.expander("👤 (01) Dados Pessoais", expanded=True):
        col1, col2 = st.columns(2)
        docente = col1.text_input("Docente:", placeholder="Nome do Professor")
        disciplina = col2.text_input("Componente Curricular:", placeholder="Nome da Disciplina")

        # Preenchimento automático da planilha (mantido)
        obs = st.text_input("Obs.:", value=str(aluno.get("Obs.", "")))

    # (02) HISTÓRICO
    hist_txt = st.text_area(
        "(02) Histórico (Origem até a atualidade):",
        value=str(aluno.get("(02) Histórico", "")),
        height=80,
    )

    # (03) e (04)
    col_a, col_b = st.columns(2)
    nec_val = col_a.text_area(
        "(03) Necessidades Educacionais:",
        value=str(aluno.get("(03) Necessidades Educacionais Específicas", "")),
    )
    hab_val = col_b.text_area(
        "(04) Conhecimentos e Habilidades:",
        value=str(aluno.get("(04) Conhecimentos e Habilidades", "")),
    )

    # (08) CONTEÚDO
    st.text_area("(08) Conteúdos Programáticos:", key="k_08", height=80)

    # AÇÃO IA
    if st.button("🚀 Gerar Sugestões e Preencher"):
        if not disciplina or not st.session_state.k_08:
            st.error("Preencha o Componente Curricular e o Conteúdo (08) primeiro.")
        else:
            with st.spinner("IA processando e preenchendo os campos..."):
                prompt = (
                    f"Gere os campos (07) Objetivos, (09) Metodologia, (10) Avaliação e (11) Resultados "
                    f"para o aluno {aluno_nome} na matéria {disciplina}. "
                    f"Baseie-se no conteúdo: {st.session_state.k_08}."
                )
                raw_response = call_maritalk(prompt)
                st.session_state.ia_raw = raw_response
                parse_and_apply_ia(raw_response)
                st.rerun()

    # Campos Editáveis (07, 09, 10, 11)
    c_left, c_right = st.columns(2)
    with c_left:
        st.text_area("(07) Objetivos Específicos:", key="k_07", height=120)
        st.text_area("(09) Metodologia:", key="k_09", height=120)
    with c_right:
        st.text_area("(10) Avaliação:", key="k_10", height=120)
        st.text_area("(11) Resultados Esperados:", key="k_11", height=120)

    # GERAR PDF
    if st.button("📥 Montar PDF Final"):
        pdf = PEI_PDF()
        pdf.add_page()

        # (01) DADOS
        pdf.section_header("(01) DADOS PESSOAIS")
        pdf.info_box(f"Nome do Estudante: {aluno_nome}")
        pdf.info_box(
            "Nome do Responsável: "
            f"{aluno.get('Nome do Pai/Mãe ou responsável', '')} | "
            f"Tel: {aluno.get('Telefone para contato', '')}"
        )
        pdf.info_box(
            "Data Nascimento: "
            f"{aluno.get('Data do Nascimento', '')} | "
            f"Idade: {aluno.get('Idade', '')}"
        )
        pdf.info_box(f"Curso: {aluno.get('Curso', '')}")
        pdf.info_box(f"Componente Curricular: {disciplina} | Docente: {docente}")

        # Seções
        pdf.section_header("(02) HISTÓRICO")
        pdf.info_box(hist_txt)

        pdf.section_header("(03) NECESSIDADES EDUCACIONAIS ESPECÍFICAS")
        pdf.info_box(nec_val)

        pdf.section_header("(04) CONHECIMENTOS E HABILIDADES")
        pdf.info_box(hab_val)

        pdf.section_header("(07) OBJETIVOS ESPECÍFICOS")
        pdf.info_box(st.session_state.k_07)

        pdf.section_header("(08) CONTEÚDOS PROGRAMÁTICOS")
        pdf.info_box(st.session_state.k_08)

        pdf.section_header("(09) METODOLOGIA")
        pdf.info_box(st.session_state.k_09)

        pdf.section_header("(10) AVALIAÇÃO")
        pdf.info_box(st.session_state.k_10)

        pdf.section_header("(11) RESULTADOS ESPERADOS")
        pdf.info_box(st.session_state.k_11)

        # ASSINATURAS
        pdf.ln(10)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 5, safe_pdf_text("(14) ASSINATURAS"), ln=True)
        pdf.ln(5)

        pdf.set_font("Arial", "", 9)
        pdf.cell(0, 6, safe_pdf_text("_________________________________________________          ____/____/________"), ln=True)
        pdf.cell(0, 6, safe_pdf_text("Assinatura do Docente"), ln=True)
        pdf.ln(4)

        pdf.cell(0, 6, safe_pdf_text("_________________________________________________          ____/____/________"), ln=True)
        pdf.cell(0, 6, safe_pdf_text("Assinatura da Coordenação de Curso"), ln=True)
        pdf.ln(4)

        pdf.cell(0, 6, safe_pdf_text("_________________________________________________          ____/____/________"), ln=True)
        pdf.cell(0, 6, safe_pdf_text("Assinatura do Departamento de Ensino"), ln=True)

        # DOWNLOAD (sem arquivo em disco)
        # fpdf2: output(dest="S") -> str; fpdf antigo: pode ser bytes/str dependendo da versão
        pdf_out = pdf.output(dest="S")
        if isinstance(pdf_out, str):
            pdf_bytes = pdf_out.encode("latin-1", errors="replace")
        else:
            pdf_bytes = bytes(pdf_out)

        st.download_button(
            "Clique aqui para baixar o PDF",
            data=pdf_bytes,
            file_name=f"PEI_{aluno_nome}.pdf",
            mime="application/pdf",
        )

