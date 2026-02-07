import os
import io
import re
import requests
import pandas as pd
import streamlit as st
from fpdf import FPDF
from streamlit_gsheets import GSheetsConnection
from datetime import datetime


# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="Gerador PEI / Atividades - IFMT", layout="wide")


# =========================================================
# SESSION STATE
# =========================================================
def init_session_keys():
    keys = [
        # PEI
        "k_07", "k_08_pei", "k_09", "k_10", "k_11", "ia_raw",
        # ATIVIDADES (widget + buffer para evitar conflito de session_state)
        "k_08_ativ", "k_12_ativ", "k_12_ativ_buf", "ia_ativ_raw",
        # UI
        "aluno_pei", "aluno_ativ", "docente_pei", "disciplina_pei",
        "docente_ativ", "disciplina_ativ",
        # extras UI
        "obs_pei", "hist_pei", "nec_pei", "hab_pei", "dif_pei", "ada_pei",
    ]
    for k in keys:
        if k not in st.session_state:
            st.session_state[k] = ""


init_session_keys()


# =========================================================
# SANITIZAÇÃO DE TEXTO PARA PDF (sem fontes externas)
# =========================================================
def safe_pdf_text(s: str) -> str:
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

    try:
        s = s.encode("cp1252", errors="replace").decode("cp1252")
    except Exception:
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
    """Extrai os blocos 07/09/10/11 e injeta no session_state (PEI)."""
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


def parse_and_apply_activities(text: str):
    """Extrai o bloco 12 e escreve no BUFFER (evita conflito com widget key='k_12_ativ')."""
    p = r"(?is)(?:\(?12\)?|12\s*[-:])\s*(.*?)(?=$)"
    m = re.search(p, text, re.DOTALL)
    if m:
        st.session_state["k_12_ativ_buf"] = m.group(1).strip()
    else:
        # fallback: não perde a resposta
        st.session_state["k_12_ativ_buf"] = (text or "").strip()


# =========================================================
# PDF (FPDF compatível fpdf2 e fpdf antigo)
# =========================================================
class BasePDF(FPDF):
    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, core_fonts_encoding="cp1252", **kwargs)
        except TypeError:
            super().__init__(*args, **kwargs)
        self.set_auto_page_break(auto=True, margin=12)

    def header_brand(self):
        self.set_font("Arial", "B", 10)
        self.cell(0, 5, safe_pdf_text("Ministério da Educação"), ln=True, align="C")
        self.cell(0, 5, safe_pdf_text("Secretaria de Educação Profissional e Tecnológica"), ln=True, align="C")
        self.cell(0, 5, safe_pdf_text("Instituto Federal de Educação, Ciência e Tecnologia de Mato Grosso"), ln=True, align="C")
        self.ln(5)

    def section_header(self, title):
        self.set_font("Arial", "B", 10)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 8, safe_pdf_text(f" {title}"), border=1, ln=True, fill=True)

    def info_box(self, content):
        self.set_font("Arial", "", 10)
        text = safe_pdf_text(content)
        self.multi_cell(0, 6, text, border=1, align="L")
        self.ln(1)


class PEI_PDF(BasePDF):
    def header(self):
        self.header_brand()
        self.set_font("Arial", "B", 12)
        self.cell(0, 7, safe_pdf_text("ANEXO II"), ln=True, align="C")
        self.cell(0, 7, safe_pdf_text("PLANO EDUCACIONAL INDIVIDUALIZADO (PEI)"), ln=True, align="C")
        self.ln(5)


class ATIV_PDF(BasePDF):
    def header(self):
        self.header_brand()
        self.set_font("Arial", "B", 12)
        self.cell(0, 7, safe_pdf_text("SUGESTÕES DE ATIVIDADES"), ln=True, align="C")
        self.ln(5)


def pdf_bytes(pdf: FPDF) -> bytes:
    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1", errors="replace")
    return bytes(out)


# =========================================================
# UI - CABEÇALHO
# =========================================================
st.markdown("""
<style>
[data-testid="stImage"] { display: flex; justify-content: center; }
</style>
""", unsafe_allow_html=True)

col_esq, col_centro, col_dir = st.columns([1, 2, 1])
with col_esq:
    st.image("ifmt_barra.png", width=100)

with col_centro:
    st.markdown("<h3 style='text-align:center; margin-top:5px;'>Gerador de PEI / Atividades - IFMT</h3>",
                unsafe_allow_html=True)

# =========================================================
# DADOS (GSHEETS)
# =========================================================
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read()
df.columns = [str(c).strip() for c in df.columns]

nomes = []
if "Nome do Estudante" in df.columns:
    nomes = df["Nome do Estudante"].dropna().unique().tolist()

st.write("Colunas encontradas:", df.columns.tolist())

# =========================================================
# ABAS
# =========================================================
tab_pei, tab_ativ = st.tabs(["📄 PEI", "📚 ATIVIDADES"])


# =========================================================
# ABA PEI
# =========================================================
with tab_pei:
    aluno_nome = st.selectbox(
        "Selecione o Estudante:",
        ["Selecione..."] + nomes,
        key="aluno_pei"
    )

    if aluno_nome != "Selecione...":
        aluno = df[df["Nome do Estudante"] == aluno_nome].iloc[0].to_dict()

        with st.expander("👤 (01) Dados Pessoais", expanded=True):
            col1, col2 = st.columns(2)
            docente = col1.text_input("Docente:", placeholder="Nome do Professor", key="docente_pei")
            disciplina = col2.text_input("Componente Curricular:", placeholder="Nome da Disciplina", key="disciplina_pei")
            obs = st.text_input("Obs.:", value=str(aluno.get("Obs.", "")), key="obs_pei")


        diag_txt = st.text_area(
            "Diagnóstico",
            value=str(aluno.get("Diagnóstico", "")),
            height=80,
            key="diag_pei",
        )

        
        hist_txt = st.text_area(
            "(02) Histórico (Origem até a atualidade):",
            value=str(aluno.get("(02) Histórico", "")),
            height=80,
            key="hist_pei",
        )

        col_a, col_b = st.columns(2)
        nec_val = col_a.text_area(
            "(03) Necessidades Educacionais:",
            value=str(aluno.get("(03) Necessidades Educacionais Específicas", "")),
            key="nec_pei",
        )
        hab_val = col_b.text_area(
            "(04) Conhecimentos e Habilidades:",
            value=str(aluno.get("(04) Conhecimentos e Habilidades", "")),
            key="hab_pei",
        )

        col_a, col_b = st.columns(2)
        dif_val = col_a.text_area(
            "(05) Dificuldades Apresentadas",
            value=str(aluno.get("(05) Dificuldades Apresentadas", "")),
            key="dif_pei",
        )
        ada_val = col_b.text_area(
            "(06) Adaptações Razoáveis e/ou Acessibilidades",
            value=str(aluno.get("(06) Adaptações Razoáveis e/ou Acessibilidades", "")),
            key="ada_pei",
        )

        st.text_area("(08) Conteúdos Programáticos:", key="k_08_pei", height=80)

        if st.button("🚀 Gerar Sugestões e Preencher (PEI)", key="btn_ia_pei"):
            if not docente or not disciplina or not st.session_state.k_08_pei:
                st.error("Preencha Docente, Componente Curricular e o Conteúdo (08) primeiro.")
            else:
                with st.spinner("IA processando e preenchendo os campos..."):
                    prompt = f"""
Você é um especialista em Educação Inclusiva e PEI no contexto do IFMT.
Sua tarefa é gerar SOMENTE os campos (07), (09), (10) e (11) do PEI, de forma individualizada,
levando em consideração TODO o contexto do estudante abaixo.

REGRAS IMPORTANTES:
1) Use EXATAMENTE este formato com numeração e títulos (para eu extrair por regex):
07 - Objetivos Específicos:
09 - Metodologia:
10 - Avaliação:
11 - Resultados Esperados:

2) Não escreva nada fora desses quatro blocos. Não inclua 08, 02, comentários, introdução, nem explicações.
3) Escreva em português, em tópicos curtos e objetivos (sem textão).
4) Seja realista e aplicável em sala (IFMT). Priorize acessibilidade, UDL/DUA e adaptações razoáveis (sem inventar diagnóstico).
5) Metodologia e avaliação devem estar coerentes com:
   - necessidades, habilidades, dificuldades e adaptações informadas
   - o conteúdo programático (08)
   - o componente curricular (disciplina)
6) Avaliação: descreva como avaliar com flexibilidade (instrumentos, tempo, forma, critérios), e como registrar evidências.
7) Resultados esperados: mensuráveis e observáveis.

DADOS DO CONTEXTO
Aluno: {aluno_nome}
Curso: {aluno.get("Curso","")}
Idade: {aluno.get("Idade","")}
Docente: {docente}
Componente Curricular: {disciplina}

(02) Histórico:
{hist_txt}

(03) Necessidades:
{nec_val}

(04) Habilidades:
{hab_val}

(05) Dificuldades:
{dif_val}

(06) Adaptações:
{ada_val}

Obs.:
{obs}

(08) Conteúdos Programáticos:
{st.session_state.k_08_pei}

AGORA GERE A SAÍDA NO FORMATO EXATO.
"""
                    raw_response = call_maritalk(prompt)
                    st.session_state.ia_raw = raw_response
                    parse_and_apply_ia(raw_response)
                    st.rerun()

        c_left, c_right = st.columns(2)
        with c_left:
            st.text_area("(07) Objetivos Específicos:", key="k_07", height=120)
            st.text_area("(09) Metodologia:", key="k_09", height=120)
        with c_right:
            st.text_area("(10) Avaliação:", key="k_10", height=120)
            st.text_area("(11) Resultados Esperados:", key="k_11", height=120)

        if st.button("📥 Montar PDF Final (PEI)", key="btn_pdf_pei"):
            pdf = PEI_PDF()
            pdf.add_page()

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
            ano_valor = aluno.get('Ano') or aluno.get('Ano/Turma') or ''
            pdf.info_box(f"Ano/Turma: {ano_valor}")
            data_hoje = datetime.now().strftime("%d/%m/%Y")
            pdf.info_box(f"Data de Preenchimento: {data_hoje}") 

        

            pdf.info_box(f"Componente Curricular: {disciplina} | Docente: {docente}")

            pdf.section_header("DIAGNÓSTICO")
            pdf.info_box(diag_txt)

            pdf.section_header("(02) HISTÓRICO")
            pdf.info_box(hist_txt)

            pdf.section_header("(03) NECESSIDADES EDUCACIONAIS ESPECÍFICAS")
            pdf.info_box(nec_val)

            pdf.section_header("(04) CONHECIMENTOS E HABILIDADES")
            pdf.info_box(hab_val)

            pdf.section_header("(05) DIFICULDADES APRESENTADAS")
            pdf.info_box(dif_val)

            pdf.section_header("(06) ADAPTAÇÕES")
            pdf.info_box(ada_val)

            pdf.section_header("(07) OBJETIVOS ESPECÍFICOS")
            pdf.info_box(st.session_state.k_07)

            pdf.section_header("(08) CONTEÚDOS PROGRAMÁTICOS")
            pdf.info_box(st.session_state.k_08_pei)

            pdf.section_header("(09) METODOLOGIA")
            pdf.info_box(st.session_state.k_09)

            pdf.section_header("(10) AVALIAÇÃO")
            pdf.info_box(st.session_state.k_10)

            pdf.section_header("(11) RESULTADOS ESPERADOS")
            pdf.info_box(st.session_state.k_11)

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

            st.download_button(
                "Clique aqui para baixar o PDF (PEI)",
                data=pdf_bytes(pdf),
                file_name=f"PEI_{aluno_nome}.pdf",
                mime="application/pdf",
                key="dl_pei",
            )


# =========================================================
# ABA ATIVIDADES (EXTERNO AO PEI)
# =========================================================
with tab_ativ:
    st.markdown("### 📚 Gerador de Atividades (externo ao PEI)")

    aluno_nome_ativ = st.selectbox(
        "Selecione o Estudante (opcional):",
        ["(Sem estudante)"] + nomes,
        key="aluno_ativ"
    )

    aluno_ativ = None
    if aluno_nome_ativ != "(Sem estudante)":
        aluno_ativ = df[df["Nome do Estudante"] == aluno_nome_ativ].iloc[0].to_dict()

    col1, col2 = st.columns(2)
    docente_ativ = col1.text_input("Docente:", placeholder="Nome do Professor", key="docente_ativ")
    disciplina_ativ = col2.text_input("Componente Curricular:", placeholder="Nome da Disciplina", key="disciplina_ativ")

    st.text_area("(08) Conteúdos Programáticos (base):", key="k_08_ativ", height=110)

    # ---- Sincronização BUFFER -> WIDGET (antes do widget nascer) ----
    if st.session_state.get("k_12_ativ_buf"):
        st.session_state["k_12_ativ"] = st.session_state["k_12_ativ_buf"]
        st.session_state["k_12_ativ_buf"] = ""  # limpa para não sobrescrever edições futuras

    st.text_area("(12) Sugestões de Atividades (editável):", key="k_12_ativ", height=280)

    if st.button("🧠 Gerar Atividades", key="btn_ia_ativ"):
        if not disciplina_ativ or not st.session_state.k_08_ativ:
            st.error("Preencha o Componente Curricular e o Conteúdo (08) primeiro.")
        else:
            hist = nec = hab = dif = ada = obs_local = ""
            curso = idade = ""
            if aluno_ativ:
                curso = str(aluno_ativ.get("Curso", ""))
                idade = str(aluno_ativ.get("Idade", ""))
                hist = str(aluno_ativ.get("(02) Histórico", ""))
                nec  = str(aluno_ativ.get("(03) Necessidades Educacionais Específicas", ""))
                hab  = str(aluno_ativ.get("(04) Conhecimentos e Habilidades", ""))
                dif  = str(aluno_ativ.get("(05) Dificuldades Apresentadas", ""))
                ada  = str(aluno_ativ.get("(06) Adaptações Razoáveis e/ou Acessibilidades", ""))
                obs_local = str(aluno_ativ.get("Obs.", ""))

            with st.spinner("IA gerando atividades..."):
                prompt_ativ = f"""
Você é especialista em planejamento didático inclusivo no IFMT.
Gere SOMENTE o bloco abaixo.

FORMATO OBRIGATÓRIO:
12 - Sugestões de Atividades:

REGRAS:
- Não escreva nada fora do bloco 12.
- Liste de 6 a 10 atividades, prontas para aplicar.
- Para cada atividade use:
  • Atividade:
  • Objetivo:
  • Materiais:
  • Como aplicar (passos):
  • Adaptações/apoios:
  • Evidência para avaliar:

CONTEXTO (se houver estudante, personalize; se não houver, mantenha genérico):
Estudante: {aluno_nome_ativ}
Curso: {curso}
Idade: {idade}
Histórico: {hist}
Necessidades: {nec}
Habilidades: {hab}
Dificuldades: {dif}
Adaptações: {ada}
Obs.: {obs_local}

Docente: {docente_ativ}
Componente Curricular: {disciplina_ativ}

Conteúdos (08):
{st.session_state.k_08_ativ}

AGORA GERE A SAÍDA NO FORMATO EXATO.
"""
                raw = call_maritalk(prompt_ativ)
                st.session_state["ia_ativ_raw"] = raw
                parse_and_apply_activities(raw)
                st.rerun()

    if st.button("📥 Montar PDF (Atividades)", key="btn_pdf_ativ"):
        pdf = ATIV_PDF()
        pdf.add_page()

        pdf.section_header("IDENTIFICAÇÃO")
        if aluno_nome_ativ == "(Sem estudante)":
            pdf.info_box("Estudante: (não selecionado)")
            pdf.info_box("Curso: ")
            pdf.info_box("Idade: ")
        else:
            pdf.info_box(f"Estudante: {aluno_nome_ativ}")
            pdf.info_box(f"Curso: {aluno_ativ.get('Curso','') if aluno_ativ else ''}")
            pdf.info_box(f"Idade: {aluno_ativ.get('Idade','') if aluno_ativ else ''}")

        pdf.info_box(f"Componente Curricular: {disciplina_ativ} | Docente: {docente_ativ}")

        pdf.section_header("CONTEÚDOS INFORMADOS (base para as atividades)")
        pdf.info_box(st.session_state.k_08_ativ)

        pdf.section_header("ATIVIDADES SUGERIDAS (editáveis)")
        pdf.info_box(st.session_state.k_12_ativ)

        st.download_button(
            "Clique aqui para baixar o PDF (Atividades)",
            data=pdf_bytes(pdf),
            file_name="Atividades.pdf",
            mime="application/pdf",
            key="dl_ativ",
        )

st.markdown("""
<hr style="margin-top: 30px; margin-bottom: 10px;">
<p style="text-align:center; color: #64748b; font-size: 13px; margin: 0;">
Protótipo desenvolvido por <b>Ricardo da Silva Santos</b> e <b>Tatiane Felipe Lopes</b>.
</p>
""", unsafe_allow_html=True)
