# app.py — Gerador de PEI (Anexo II) completo e robusto (Streamlit + GSheets + Maritaca + PDF)
import os
import io
import re
import tempfile
import requests
import pandas as pd
import streamlit as st
from fpdf import FPDF
from streamlit_gsheets import GSheetsConnection

# ============================
# CONFIG
# ============================
st.set_page_config(page_title="Gerador PEI - IFMT", layout="wide")
st.title("🌿 Gerador de PEI Oficial - IFMT")

# ============================
# HELPERS
# ============================
def s(value) -> str:
    """Converte valores (incluindo NaN) em string segura."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()

def safe_get(d: dict, key: str, default=""):
    return s(d.get(key, default))

def call_maritalk(prompt: str) -> str:
    """Chamada à API da Maritaca (sabia-3)."""
    try:
        api_key = st.secrets["MARITALK_API_KEY"]
        url = "https://chat.maritaca.ai/api/chat/completions"
        headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "sabia-3",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1600,
            "temperature": 0.6,
        }
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        j = r.json()
        return j["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Erro ao gerar sugestão automática via IA: {e}"

def parse_ia_blocks(text: str) -> dict:
    """
    Extrai blocos (07), (09), (10), (11) do texto retornado pela IA.
    Aceita variações tipo:
    (07) ...
    07) ...
    (09) ...
    """
    out = {"07": "", "09": "", "10": "", "11": ""}
    if not text:
        return out

    # normaliza
    t = text.replace("\r", "")
    # marcações possíveis
    pattern = re.compile(r"(?P<tag>\(?0?7\)?|\(?0?9\)?|\(?10\)?|\(?11\)?)\s*[-:)]\s*", re.IGNORECASE)

    # encontra posições
    matches = list(pattern.finditer(t))
    if not matches:
        return out

    # cria fatias
    for i, m in enumerate(matches):
        tag_raw = m.group("tag")
        tag = re.sub(r"[^\d]", "", tag_raw)  # só números
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(t)
        chunk = t[start:end].strip()
        if tag in out:
            out[tag] = chunk

    return out

# ============================
# PDF (Padrão Anexo II)
# ============================
class PEI_PDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=12)
        self.set_margins(12, 12, 12)

        # Fonte Unicode para acentos (Streamlit Cloud geralmente tem)
        self.font_regular = "DejaVu"
        self.font_bold = "DejaVuB"

        dejavu = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        dejavub = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if os.path.exists(dejavu) and os.path.exists(dejavub):
            self.add_font(self.font_regular, "", dejavu, uni=True)
            self.add_font(self.font_bold, "", dejavub, uni=True)
        else:
            # fallback
            self.font_regular = "Arial"
            self.font_bold = "Arial"

    def header(self):
        self.set_font(self.font_bold, "", 10)
        self.cell(0, 5, "Ministério da Educação", ln=True, align="C")
        self.cell(0, 5, "Secretaria de Educação Profissional e Tecnológica", ln=True, align="C")
        self.cell(0, 5, "Instituto Federal de Educação, Ciência e Tecnologia do Instituto Federal de Mato Grosso", ln=True, align="C")
        self.ln(2)

        self.set_font(self.font_bold, "", 12)
        self.cell(0, 7, "ANEXO II", ln=True, align="C")
        self.cell(0, 7, "PLANO EDUCACIONAL INDIVIDUALIZADO (PEI)", ln=True, align="C")
        self.ln(3)

    def section_bar(self, text):
        self.set_font(self.font_bold, "", 10)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 7, text, ln=True, fill=True, border=1)
        self.ln(2)

    def field_line(self, label, value="", h=7):
        self.set_font(self.font_bold, "", 10)
        self.cell(55, h, f"{label}:", border=1, ln=0)
        self.set_font(self.font_regular, "", 10)
        self.cell(0, h, s(value), border=1, ln=1)

    def field_two_cols(self, left_label, left_value, right_label, right_value, h=7, split=0.58):
        total_w = self.w - self.l_margin - self.r_margin
        left_w = total_w * split
        right_w = total_w - left_w

        # Left
        self.set_font(self.font_bold, "", 10)
        self.cell(left_w * 0.38, h, f"{left_label}:", border=1, ln=0)
        self.set_font(self.font_regular, "", 10)
        self.cell(left_w * 0.62, h, s(left_value), border=1, ln=0)

        # Right
        self.set_font(self.font_bold, "", 10)
        self.cell(right_w * 0.42, h, f"{right_label}:", border=1, ln=0)
        self.set_font(self.font_regular, "", 10)
        self.cell(right_w * 0.58, h, s(right_value), border=1, ln=1)

    def big_box(self, text, min_h=22):
        x = self.get_x()
        y = self.get_y()
        w = self.w - self.l_margin - self.r_margin

        self.set_font(self.font_regular, "", 10)
        # dry run para estimar altura
        start_y = self.get_y()
        self.multi_cell(w, 5, s(text), border=0)
        used_h = self.get_y() - start_y

        box_h = max(min_h, used_h + 4)

        # desenha caixa
        self.set_xy(x, y)
        self.rect(x, y, w, box_h)

        # escreve texto dentro
        self.set_xy(x + 1.5, y + 1.5)
        self.multi_cell(w - 3, 5, s(text), border=0)

        # posiciona abaixo
        self.set_xy(x, y + box_h + 2)

    def signature_row(self, label_left, label_right="Data:"):
        total_w = self.w - self.l_margin - self.r_margin
        left_w = total_w * 0.7
        right_w = total_w - left_w

        self.ln(2)
        self.set_font(self.font_regular, "", 10)
        self.cell(left_w, 6, "_______________________________", ln=0, align="L")
        self.cell(right_w, 6, "____/____/________", ln=1, align="R")
        self.cell(left_w, 6, label_left, ln=0, align="L")
        self.cell(right_w, 6, label_right, ln=1, align="R")

def pdf_to_bytes(pdf: PEI_PDF) -> bytes:
    """
    Conversão robusta para bytes.
    Evita o erro do Streamlit 'unsupported_error' no download_button.
    """
    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1", errors="replace")
    return bytes(out)

def pdf_to_tempfile_and_open(pdf: PEI_PDF):
    """
    Alternativa ainda mais robusta (Streamlit Cloud): escreve em arquivo temporário e abre em modo rb.
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_path = tmp.name
    tmp.close()
    pdf.output(tmp_path)
    return tmp_path

# ============================
# CONEXÃO GSheets
# ============================
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
except Exception as e:
    st.error(f"Erro na conexão com a planilha: {e}")
    st.stop()

# ============================
# MAPA DE COLUNAS (PLANILHA)
# ============================
COL_NOME = "Nome do Estudante"
COL_RESP = "Nome do Pai/Mãe ou responsável"
COL_OBS = "Obs."  # opcional
COL_TEL = "Telefone para contato"
COL_NASC = "Data do Nascimento"
COL_IDADE = "Idade"
COL_CURSO = "Curso"
COL_HIST = "(02) Histórico"
COL_NECESSIDADE = "(03) Necessidades Educacionais Específicas"
COL_HAB = "(04) Conhecimentos e Habilidades"
COL_DIF = "(05) Dificuldades Apresentadas"
COL_ADAPT = "(06) Adaptações Razoáveis e/ou Acessibilidades"

if COL_NOME not in df.columns:
    st.error(f"Coluna obrigatória ausente: '{COL_NOME}'.")
    st.stop()

# ============================
# UI — SELEÇÃO DE ALUNO
# ============================
aluno_nome = st.selectbox("Selecione o Estudante:", ["Selecione..."] + df[COL_NOME].astype(str).tolist())

if aluno_nome == "Selecione...":
    st.info("Selecione um estudante para preencher o PEI.")
    st.stop()

aluno_row = df[df[COL_NOME].astype(str) == str(aluno_nome)].iloc[0]
aluno = aluno_row.to_dict()

st.subheader("📝 Preenchimento do Plano")

# ============================
# (01) DADOS PESSOAIS
# ============================
c1, c2, c3 = st.columns(3)
with c1:
    docente_input = st.text_input("Docente:", value="")
with c2:
    materia_input = st.text_input("Componente Curricular:", value="")
with c3:
    obs_input = st.text_input("Obs. (responsável):", value=s(aluno.get(COL_OBS, "")))

# ============================
# (02) HISTÓRICO EDITÁVEL
# ============================
hist_original = s(aluno.get(COL_HIST, ""))
texto_historico = st.text_area("(02) Histórico (Edite se necessário):", value=hist_original, height=120)

# ============================
# (03)-(06) VISUALIZAÇÃO / EDIÇÃO OPCIONAL
# ============================
with st.expander("Ver/editar (03) a (06) (opcional)"):
    necessidade_03 = st.text_area("(03) Necessidades Educacionais Específicas:", value=s(aluno.get(COL_NECESSIDADE, "")), height=100)
    hab_04 = st.text_area("(04) Conhecimentos e Habilidades:", value=s(aluno.get(COL_HAB, "")), height=100)
    dif_05 = st.text_area("(05) Dificuldades Apresentadas:", value=s(aluno.get(COL_DIF, "")), height=100)
    adapt_06 = st.text_area("(06) Adaptações Razoáveis/Acessibilidades:", value=s(aluno.get(COL_ADAPT, "")), height=100)

# ============================
# (07)-(11)
# ============================
st.markdown("### Desenvolvimento pedagógico (07)–(11)")
conteudo_input = st.text_area("(08) Conteúdos Programáticos:", height=90)

colA, colB = st.columns(2)
with colA:
    objetivos_07 = st.text_area("(07) Objetivos Específicos:", height=140)
    metodologia_09 = st.text_area("(09) Metodologia:", height=140)
with colB:
    avaliacao_10 = st.text_area("(10) Avaliação:", height=140)
    resultados_11 = st.text_area("(11) Resultados Esperados:", height=140)

# IA
if st.button("🚀 Gerar Sugestões (IA) para (07), (09), (10) e (11)"):
    if not materia_input or not conteudo_input:
        st.warning("Preencha 'Componente Curricular' e '(08) Conteúdos Programáticos' para a IA sugerir.")
    else:
        prompt = f"""
Você é um especialista em PEI (Plano Educacional Individualizado) e educação inclusiva.
Gere sugestões OBJETIVAS e PRÁTICAS, em PT-BR, com bullets curtos.

Use exatamente o formato:
(07) <texto>
(09) <texto>
(10) <texto>
(11) <texto>

Contexto:
Estudante: {safe_get(aluno, COL_NOME)}
Curso: {safe_get(aluno, COL_CURSO)}
Componente Curricular: {materia_input}
Necessidades (03): {necessidade_03 if 'necessidade_03' in locals() else safe_get(aluno, COL_NECESSIDADE)}
Habilidades (04): {hab_04 if 'hab_04' in locals() else safe_get(aluno, COL_HAB)}
Dificuldades (05): {dif_05 if 'dif_05' in locals() else safe_get(aluno, COL_DIF)}
Adaptações (06): {adapt_06 if 'adapt_06' in locals() else safe_get(aluno, COL_ADAPT)}
Conteúdos (08): {conteudo_input}
"""
        st.session_state["ia_raw"] = call_maritalk(prompt)
        blocks = parse_ia_blocks(st.session_state["ia_raw"])
        # só preenche se vier algo
        st.session_state["ia_07"] = blocks.get("07", "")
        st.session_state["ia_09"] = blocks.get("09", "")
        st.session_state["ia_10"] = blocks.get("10", "")
        st.session_state["ia_11"] = blocks.get("11", "")

if "ia_raw" in st.session_state:
    st.text_area("📌 Sugestões brutas da IA (referência):", value=st.session_state["ia_raw"], height=140)

# Botão para aplicar sugestões aos campos
if any(k in st.session_state for k in ["ia_07", "ia_09", "ia_10", "ia_11"]):
    if st.button("✅ Aplicar sugestões da IA nos campos"):
        if st.session_state.get("ia_07"):
            objetivos_07 = st.session_state["ia_07"]
        if st.session_state.get("ia_09"):
            metodologia_09 = st.session_state["ia_09"]
        if st.session_state.get("ia_10"):
            avaliacao_10 = st.session_state["ia_10"]
        if st.session_state.get("ia_11"):
            resultados_11 = st.session_state["ia_11"]
        st.success("Sugestões aplicadas. (Se quiser, revise os campos antes de gerar o PDF.)")

# ============================
# (12)-(13)
# ============================
b1, b2 = st.columns(2)
with b1:
    bib_b = st.text_input("(12) Bibliografia Básica:", value="Conforme o PPC do curso.")
with b2:
    bib_c = st.text_input("(13) Bibliografia Complementar:", value="Materiais adaptados e recursos digitais.")

# ============================
# GERAR PDF
# ============================
st.markdown("---")
st.subheader("📄 Gerar PDF")

col_pdf1, col_pdf2 = st.columns([1, 1])
with col_pdf1:
    use_tempfile = st.checkbox("Usar modo ultra-robusto (arquivo temporário)", value=True)
with col_pdf2:
    st.caption("Se estiver na Streamlit Cloud e der erro no download, deixe marcado.")

if st.button("📌 Montar PDF (Anexo II)"):
    pdf = PEI_PDF()
    pdf.add_page()

    # (01)
    pdf.section_bar("(01) DADOS PESSOAIS")
    pdf.field_line("Nome do Estudante", safe_get(aluno, COL_NOME))
    pdf.field_two_cols("Nome do Pai/Mãe ou responsável", safe_get(aluno, COL_RESP), "Obs.", obs_input)
    pdf.field_two_cols("Telefone para contato", safe_get(aluno, COL_TEL), "Data do Nascimento", safe_get(aluno, COL_NASC))
    pdf.field_two_cols("Idade", safe_get(aluno, COL_IDADE), "Curso", safe_get(aluno, COL_CURSO))
    pdf.field_two_cols("Componente Curricular", materia_input, "Docente", docente_input)

    # (02)
    pdf.section_bar("(02) HISTÓRICO (ANTERIOR, EM INSTITUIÇÃO DE ORIGEM ATÉ A ATUALIDADE)")
    pdf.big_box(texto_historico, min_h=28)

    # (03)
    pdf.section_bar("(03) NECESSIDADES EDUCACIONAIS ESPECÍFICAS")
    pdf.big_box(necessidade_03 if 'necessidade_03' in locals() else safe_get(aluno, COL_NECESSIDADE), min_h=20)

    # (04)
    pdf.section_bar("(04) CONHECIMENTOS, HABILIDADES, CAPACIDADES, INTERESSES, NECESSIDADES")
    pdf.big_box(hab_04 if 'hab_04' in locals() else safe_get(aluno, COL_HAB), min_h=20)

    # (05)
    pdf.section_bar("(05) DIFICULDADES APRESENTADAS")
    pdf.big_box(dif_05 if 'dif_05' in locals() else safe_get(aluno, COL_DIF), min_h=20)

    # (06)
    pdf.section_bar("(06) ADAPTAÇÕES RAZOÁVEIS E/OU ACESSIBILIDADES CURRICULARES")
    pdf.big_box(adapt_06 if 'adapt_06' in locals() else safe_get(aluno, COL_ADAPT), min_h=20)

    # (07)
    pdf.section_bar("(07) OBJETIVOS ESPECÍFICOS")
    pdf.big_box(objetivos_07, min_h=18)

    # (08)
    pdf.section_bar("(08) CONTEÚDOS PROGRAMÁTICOS")
    pdf.big_box(conteudo_input, min_h=18)

    # (09)
    pdf.section_bar("(09) METODOLOGIA")
    pdf.big_box(metodologia_09, min_h=18)

    # (10)
    pdf.section_bar("(10) AVALIAÇÃO")
    pdf.big_box(avaliacao_10, min_h=18)

    # (11)
    pdf.section_bar("(11) RESULTADOS ESPERADOS")
    pdf.big_box(resultados_11, min_h=18)

    # (12)
    pdf.section_bar("(12) BIBLIOGRAFIA BÁSICA")
    pdf.big_box(bib_b, min_h=16)

    # (13)
    pdf.section_bar("(13) BIBLIOGRAFIA COMPLEMENTAR")
    pdf.big_box(bib_c, min_h=16)

    # (14)
    pdf.section_bar("(14) ASSINATURAS")
    pdf.signature_row("Assinatura do Docente:", "Data:")
    pdf.signature_row("Assinatura da Coordenação de Curso:", "Data:")
    pdf.signature_row("Assinatura do Departamento de Ensino:", "Data:")

    # ---- DOWNLOAD: duas opções robustas ----
    if use_tempfile:
        tmp_path = pdf_to_tempfile_and_open(pdf)
        with open(tmp_path, "rb") as f:
            st.download_button(
                label="📥 Baixar PDF Finalizado",
                data=f,
                file_name=f"PEI_{aluno_nome}.pdf",
                mime="application/pdf",
            )
    else:
        pdf_bytes = pdf_to_bytes(pdf)
        st.download_button(
            label="📥 Baixar PDF Finalizado",
            data=io.BytesIO(pdf_bytes),
            file_name=f"PEI_{aluno_nome}.pdf",
            mime="application/pdf",
        )

    st.success("PDF montado! Use o botão de download acima.")


