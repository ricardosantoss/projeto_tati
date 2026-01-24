# app.py — Gerador de PEI (Anexo II) COMPLETO
# ✅ PDF alinhado + sem duplicação + logo IFMT
# ✅ IA gera (07/09/10/11)
# ✅ "Aplicar sugestões" FUNCIONA (callback on_click, sem StreamlitAPIException)
# ✅ download robusto (tempfile)

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
st.set_page_config(page_title="Gerador PEI - IFMT", layout="wide")
st.title("🌿 Gerador de PEI Oficial - IFMT")

# =========================================================
# HELPERS
# =========================================================
def s(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()

def call_maritalk(prompt: str) -> str:
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
    out = {"07": "", "09": "", "10": "", "11": ""}
    if not text:
        return out

    t = text.replace("\r", "")
    pattern = re.compile(r"(?P<tag>\(?0?7\)?|\(?0?9\)?|\(?10\)?|\(?11\)?)\s*[-:)]\s*", re.IGNORECASE)
    matches = list(pattern.finditer(t))
    if not matches:
        return out

    for i, m in enumerate(matches):
        tag = re.sub(r"[^\d]", "", m.group("tag"))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(t)
        chunk = t[start:end].strip()
        if tag in out:
            out[tag] = chunk

    return out

# =========================================================
# STATE INIT (antes de qualquer widget com key)
# =========================================================
def init_state():
    defaults = {
        "k_07": "",
        "k_08": "",
        "k_09": "",
        "k_10": "",
        "k_11": "",
        "ia_raw": "",
        "ia_07": "",
        "ia_09": "",
        "ia_10": "",
        "ia_11": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# =========================================================
# CALLBACKS (solução do erro)
# =========================================================
def apply_ia_to_fields():
    """Aplica sugestões aos campos controlados (k_07..k_11) via callback."""
    if sts := st.session_state:
        if s(R := R := R):  # noop para evitar lint, ignore
            pass

    if st.session_state.get("ia_07"):
        st.session_state["k_07"] = st.session_state["ia_07"]
    if st.session_state.get("ia_09"):
        st.session_state["k_09"] = st.session_state["ia_09"]
    if st.session_state.get("ia_10"):
        st.session_state["k_10"] = st.session_state["ia_10"]
    if st.session_state.get("ia_11"):
        st.session_state["k_11"] = st.session_state["ia_11"]
    st.session_state["applied_ok"] = True

def clear_ia():
    st.session_state["ia_raw"] = ""
    st.session_state["ia_07"] = ""
    st.session_state["ia_09"] = ""
    st.session_state["ia_10"] = ""
    st.session_state["ia_11"] = ""

# =========================================================
# PDF (Padrão ANEXO II) — CORRIGIDO + LOGO
# =========================================================
class PEI_PDF(FPDF):
    def __init__(self, logo_path: str | None = None):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=12)
        self.set_margins(12, 12, 12)

        self.font_regular = "DejaVu"
        self.font_bold = "DejaVuB"
        dejavu = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        dejavub = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

        if os.path.exists(dejavu) and os.path.exists(dejavub):
            self.add_font(self.font_regular, "", dejavu, uni=True)
            self.add_font(self.font_bold, "", dejavub, uni=True)
        else:
            self.font_regular = "Arial"
            self.font_bold = "Arial"

        self.SECTION_H = 7
        self.PAD = 1.6
        self.logo_path = logo_path if logo_path and os.path.exists(logo_path) else None

    def header(self):
        if self.logo_path:
            try:
                img_w = 26
                x = (self.w - img_w) / 2
                y = 10
                self.image(self.logo_path, x=x, y=y, w=img_w)
                self.ln(18)
            except Exception:
                self.ln(2)
        else:
            self.ln(2)

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
        self.cell(0, self.SECTION_H, text, ln=True, fill=True, border=1)
        self.ln(2)

    def _cell_fit(self, w, h, txt, border=1, ln=0, align="L", bold=False):
        base = 10
        min_size = 7
        font = self.font_bold if bold else self.font_regular
        t = str(txt) if txt is not None else ""

        self.set_font(font, "", base)
        while self.get_string_width(t) > (w - 2) and base > min_size:
            base -= 1
            self.set_font(font, "", base)

        self.cell(w, h, t, border=border, ln=ln, align=align)
        self.set_font(self.font_regular, "", 10)

    def row_2(self, label, value, label_w=65, h=7):
        total_w = self.w - self.l_margin - self.r_margin
        value_w = total_w - label_w
        self._cell_fit(label_w, h, label, border=1, ln=0, bold=True)
        self.set_font(self.font_regular, "", 10)
        self.cell(value_w, h, s(value), border=1, ln=1)

    def row_4(self, label1, val1, label2, val2, w1=65, w3=18, h=7):
        total_w = self.w - self.l_margin - self.r_margin
        remaining = total_w - (w1 + w3)
        w2 = remaining * 0.62
        w4 = remaining - w2

        self._cell_fit(w1, h, label1, border=1, ln=0, bold=True)
        self.set_font(self.font_regular, "", 10)
        self.cell(w2, h, s(val1), border=1, ln=0)

        self._cell_fit(w3, h, label2, border=1, ln=0, bold=True)
        self.set_font(self.font_regular, "", 10)
        self.cell(w4, h, s(val2), border=1, ln=1)

    def row_4_custom(self, label1, val1, label2, val2, w1=65, w2=70, w3=45, h=7):
        total_w = self.w - self.l_margin - self.r_margin
        w4 = total_w - (w1 + w2 + w3)

        self._cell_fit(w1, h, label1, border=1, ln=0, bold=True)
        self.set_font(self.font_regular, "", 10)
        self.cell(w2, h, s(val1), border=1, ln=0)

        self._cell_fit(w3, h, label2, border=1, ln=0, bold=True)
        self.set_font(self.font_regular, "", 10)
        self.cell(w4, h, s(val2), border=1, ln=1)

    def big_box(self, text, min_h=28):
        x = self.get_x()
        y = self.get_y()
        w = self.w - self.l_margin - self.r_margin
        t = s(text)

        self.set_font(self.font_regular, "", 10)

        try:
            lines = self.multi_cell(w - 2*self.PAD, 5, t, border=0, split_only=True)
            n_lines = max(1, len(lines))
            used_h = n_lines * 5
        except TypeError:
            avg_chars = max(24, int((w - 2*self.PAD) / 2.2))
            n_lines = 0
            for p in t.split("\n"):
                p = p.strip()
                if not p:
                    n_lines += 1
                    continue
                n_lines += max(1, (len(p) // avg_chars) + 1)
            used_h = max(1, n_lines) * 5

        box_h = max(min_h, used_h + 2*self.PAD + 2)

        self.rect(x, y, w, box_h)
        self.set_xy(x + self.PAD, y + self.PAD)
        self.multi_cell(w - 2*self.PAD, 5, t, border=0)
        self.set_xy(x, y + box_h + 2)

    def signatures(self):
        self.section_bar("(14) ASSINATURAS")
        total_w = self.w - self.l_margin - self.r_margin
        left_w = total_w * 0.72
        right_w = total_w - left_w

        self.ln(1)
        self.set_font(self.font_regular, "", 10)

        for label in [
            "Assinatura do Docente:",
            "Assinatura da Coordenação de Curso:",
            "Assinatura do Departamento de Ensino:"
        ]:
            self.cell(left_w, 6, "_______________________________", ln=0, align="L")
            self.cell(right_w, 6, "____/____/________", ln=1, align="R")
            self.cell(left_w, 6, label, ln=0, align="L")
            self.cell(right_w, 6, "Data:", ln=1, align="R")
            self.ln(1)

def pdf_to_tempfile(pdf: PEI_PDF) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_path = tmp.name
    tmp.close()
    pdf.output(tmp_path)
    return tmp_path

# =========================================================
# CONEXÃO GSheets
# =========================================================
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
except Exception as e:
    st.error(f"Erro na conexão com a planilha: {e}")
    st.stop()

# =========================================================
# MAPA COLUNAS
# =========================================================
COL_NOME = "Nome do Estudante"
COL_RESP = "Nome do Pai/Mãe ou responsável"
COL_OBS = "Obs."
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

# =========================================================
# UI — SELEÇÃO
# =========================================================
aluno_nome = st.selectbox("Selecione o Estudante:", ["Selecione..."] + df[COL_NOME].astype(str).tolist())
if aluno_nome == "Selecione...":
    st.info("Selecione um estudante para preencher o PEI.")
    st.stop()

aluno_row = df[df[COL_NOME].astype(str) == str(aluno_nome)].iloc[0]
aluno = aluno_row.to_dict()

st.subheader("📝 Preenchimento do Plano")

# (01) extras
c1, c2, c3 = st.columns(3)
with c1:
    docente_input = st.text_input("Docente:", value="")
with c2:
    materia_input = st.text_input("Componente Curricular:", value="")
with c3:
    obs_input = st.text_input("Obs. (responsável):", value=s(aluno.get(COL_OBS, "")))

# (02)
texto_historico = st.text_area("(02) Histórico (Edite se necessário):", value=s(aluno.get(COL_HIST, "")), height=120)

# (03)-(06)
with st.expander("Ver/editar (03) a (06) (opcional)", expanded=False):
    necessidade_val = st.text_area("(03) Necessidades Educacionais Específicas:", value=s(aluno.get(COL_NECESSIDADE, "")), height=90)
    hab_val = st.text_area("(04) Conhecimentos e Habilidades:", value=s(aluno.get(COL_HAB, "")), height=90)
    dif_val = st.text_area("(05) Dificuldades Apresentadas:", value=s(aluno.get(COL_DIF, "")), height=90)
    adapt_val = st.text_area("(06) Adaptações Razoáveis/Acessibilidades:", value=s(aluno.get(COL_ADAPT, "")), height=90)

# se expander não foi aberto, garante defaults
if "necessidade_val" not in locals():
    necessidade_val = s(aluno.get(COL_NECESSIDADE, ""))
    hab_val = s(aluno.get(COL_HAB, ""))
    dif_val = s(aluno.get(COL_DIF, ""))
    adapt_val = s(aluno.get(COL_ADAPT, ""))

# =========================================================
# (07)-(11) — CONTROLADOS
# =========================================================
st.markdown("### Desenvolvimento pedagógico (07)–(11)")

st.text_area("(08) Conteúdos Programáticos:", height=90, key="k_08")

colA, colB = st.columns(2)
with colA:
    st.text_area("(07) Objetivos Específicos:", height=140, key="k_07")
    st.text_area("(09) Metodologia:", height=140, key="k_09")
with colB:
    st.text_area("(10) Avaliação:", height=140, key="k_10")
    st.text_area("(11) Resultados Esperados:", height=140, key="k_11")

# IA
col_btn1, col_btn2 = st.columns([1, 1])
with col_btn1:
    if st.button("🚀 Gerar Sugestões (IA)"):
        if not materia_input or not st.session_state["k_08"].strip():
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
Estudante: {s(aluno.get(COL_NOME))}
Curso: {s(aluno.get(COL_CURSO))}
Componente Curricular: {materia_input}
Necessidades (03): {necessidade_val}
Habilidades (04): {hab_val}
Dificuldades (05): {dif_val}
Adaptações (06): {adapt_val}
Conteúdos (08): {st.session_state["k_08"]}
"""
            ia_raw = call_maritalk(prompt)
            st.session_state["ia_raw"] = ia_raw
            blocks = parse_ia_blocks(ia_raw)
            st.session_state["ia_07"] = blocks.get("07", "")
            st.session_state["ia_09"] = blocks.get("09", "")
            st.session_state["ia_10"] = blocks.get("10", "")
            st.session_state["ia_11"] = blocks.get("11", "")

with col_btn2:
    st.button("🧹 Limpar IA", on_click=clear_ia)

if st.session_state.get("ia_raw"):
    st.text_area("📌 Sugestões brutas da IA:", value=st.session_state["ia_raw"], height=140)

# ✅ Aplicar com CALLBACK (resolve seu erro)
if any(st.session_state.get(k) for k in ["ia_07", "ia_09", "ia_10", "ia_11"]):
    st.button("✅ Aplicar sugestões da IA nos campos", on_click=apply_ia_to_fields)

if st.session_state.get("applied_ok"):
    st.success("Sugestões aplicadas nos campos (07/09/10/11).")
    st.session_state["applied_ok"] = False

# (12)-(13)
b1, b2 = st.columns(2)
with b1:
    bib_b = st.text_input("(12) Bibliografia Básica:", value="Conforme o PPC do curso.")
with b2:
    bib_c = st.text_input("(13) Bibliografia Complementar:", value="Materiais adaptados e recursos digitais.")

# =========================================================
# GERAR PDF
# =========================================================
st.markdown("---")
st.subheader("📄 PDF no padrão do Anexo II (com logo IFMT)")

use_tempfile = st.checkbox("Modo ultra-robusto (arquivo temporário) — recomendado na Streamlit Cloud", value=True)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(APP_DIR, "images (1).png")  # coloque esse arquivo junto do app.py

if st.button("📌 Montar PDF"):
    pdf = PEI_PDF(logo_path=LOGO_PATH)
    pdf.add_page()

    # (01)
    pdf.section_bar("(01) DADOS PESSOAIS")
    pdf.row_2("Nome do Estudante:", s(aluno.get(COL_NOME)))
    pdf.row_4("Nome do Pai/Mãe ou responsável:", s(aluno.get(COL_RESP)), "Obs.:", obs_input, w1=65, w3=18)
    pdf.row_4_custom("Telefone para contato:", s(aluno.get(COL_TEL)), "Data do Nascimento:", s(aluno.get(COL_NASC)), w1=65, w2=70, w3=45)
    pdf.row_4_custom("Idade:", s(aluno.get(COL_IDADE)), "Curso:", s(aluno.get(COL_CURSO)), w1=65, w2=70, w3=45)
    pdf.row_4_custom("Componente Curricular:", materia_input, "Docente:", docente_input, w1=65, w2=70, w3=45)

    # (02)
    pdf.section_bar("(02) HISTÓRICO (ANTERIOR, EM INSTITUIÇÃO DE ORIGEM ATÉ A ATUALIDADE)")
    pdf.big_box(texto_historico, min_h=28)

    # (03)-(06)
    pdf.section_bar("(03) NECESSIDADES EDUCACIONAIS ESPECÍFICAS")
    pdf.big_box(necessidade_val, min_h=20)

    pdf.section_bar("(04) CONHECIMENTOS, HABILIDADES, CAPACIDADES, INTERESSES, NECESSIDADES")
    pdf.big_box(hab_val, min_h=20)

    pdf.section_bar("(05) DIFICULDADES APRESENTADAS")
    pdf.big_box(dif_val, min_h=20)

    pdf.section_bar("(06) ADAPTAÇÕES RAZOÁVEIS E/OU ACESSIBILIDADES CURRICULARES")
    pdf.big_box(adapt_val, min_h=20)

    # (07)-(11) — do session_state
    pdf.section_bar("(07) OBJETIVOS ESPECÍFICOS")
    pdf.big_box(st.session_state["k_07"], min_h=18)

    pdf.section_bar("(08) CONTEÚDOS PROGRAMÁTICOS")
    pdf.big_box(st.session_state["k_08"], min_h=18)

    pdf.section_bar("(09) METODOLOGIA")
    pdf.big_box(st.session_state["k_09"], min_h=18)

    pdf.section_bar("(10) AVALIAÇÃO")
    pdf.big_box(st.session_state["k_10"], min_h=18)

    pdf.section_bar("(11) RESULTADOS ESPERADOS")
    pdf.big_box(st.session_state["k_11"], min_h=18)

    # (12)-(13)
    pdf.section_bar("(12) BIBLIOGRAFIA BÁSICA")
    pdf.big_box(bib_b, min_h=16)

    pdf.section_bar("(13) BIBLIOGRAFIA COMPLEMENTAR")
    pdf.big_box(bib_c, min_h=16)

    # (14)
    pdf.signatures()

    if use_tempfile:
        tmp_path = pdf_to_tempfile(pdf)
        with open(tmp_path, "rb") as f:
            st.download_button(
                label="📥 Baixar PDF Finalizado",
                data=f,
                file_name=f"PEI_{aluno_nome}.pdf",
                mime="application/pdf",
            )
    else:
        out = pdf.output(dest="S")
        pdf_bytes = out.encode("latin-1", errors="replace") if isinstance(out, str) else bytes(out)
        st.download_button(
            label="📥 Baixar PDF Finalizado",
            data=io.BytesIO(pdf_bytes),
            file_name=f"PEI_{aluno_nome}.pdf",
            mime="application/pdf",
        )

    st.success("PDF montado! Use o botão de download acima.")




