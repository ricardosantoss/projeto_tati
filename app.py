import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import requests
from fpdf import FPDF
import os

# ----------------------------
# CONFIGURAÇÃO DA PÁGINA
# ----------------------------
st.set_page_config(page_title="Gerador PEI - IFMT", layout="wide")
st.title("🌿 Gerador de PEI Oficial - IFMT")

# ----------------------------
# UTILITÁRIOS
# ----------------------------
def s(value) -> str:
    """Converte valores (incluindo NaN) para string segura."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()

def call_maritalk(prompt: str) -> str:
    """Chamada à API da Maritaca (sabia-3)."""
    try:
        api_key = st.secrets["MARITALK_API_KEY"]
        url = "https://chat.maritaca.ai/api/chat/completions"
        headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
        data = {
            "model": "sabia-3",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1800,
            "temperature": 0.6
        }
        r = requests.post(url, headers=headers, json=data, timeout=60)
        r.raise_for_status()
        j = r.json()
        return j["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Erro ao gerar sugestão automática via IA: {e}"

# ----------------------------
# PDF (PADRÃO ANEXO II)
# ----------------------------
class PEI_PDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=12)
        self.set_margins(12, 12, 12)

        # Fonte Unicode (acentos PT-BR)
        # (em Linux, normalmente existe)
        self.font_regular = "DejaVu"
        self.font_bold = "DejaVuB"

        dejavu = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        dejavub = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if os.path.exists(dejavu) and os.path.exists(dejavub):
            self.add_font(self.font_regular, "", dejavu, uni=True)
            self.add_font(self.font_bold, "", dejavub, uni=True)
        else:
            # fallback (pode perder acentos se não houver a fonte)
            self.font_regular = "Arial"
            self.font_bold = "Arial"

    def header(self):
        self.set_font(self.font_bold, "", 10)
        self.cell(0, 5, "Ministério da Educação", ln=True, align="C")
        self.cell(0, 5, "Secretaria de Educação Profissional e Tecnológica", ln=True, align="C")
        self.cell(0, 5, "Instituto Federal de Educação, Ciência e Tecnologia do Instituto Federal de Mato Grosso", ln=True, align="C")
        self.ln(2)

        # Bloco ANEXO II / Título (como no modelo)
        self.set_font(self.font_bold, "", 12)
        self.cell(0, 7, "ANEXO II", ln=True, align="C")
        self.cell(0, 7, "PLANO EDUCACIONAL INDIVIDUALIZADO (PEI)", ln=True, align="C")
        self.ln(3)

    # --- Helpers de layout ---
    def section_bar(self, text):
        self.set_font(self.font_bold, "", 10)
        self.set_fill_color(240, 240, 240)
        self.cell(0, 7, text, ln=True, fill=True, border=1)
        self.ln(2)

    def field_line(self, label, value="", h=7):
        """Linha: 'Label: [valor]' em uma caixa."""
        self.set_font(self.font_bold, "", 10)
        self.cell(55, h, f"{label}:", border=1, ln=0)
        self.set_font(self.font_regular, "", 10)
        self.cell(0, h, s(value), border=1, ln=1)

    def field_two_cols(self, left_label, left_value, right_label, right_value, h=7, split=0.58):
        """Duas colunas na mesma linha, com caixas."""
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

    def big_box(self, text, min_h=28):
        """Caixa grande para textos longos (MultiCell com borda)."""
        x = self.get_x()
        y = self.get_y()
        w = self.w - self.l_margin - self.r_margin

        # calcula altura aproximada com multi_cell "dry run"
        self.set_font(self.font_regular, "", 10)
        start_y = self.get_y()
        self.multi_cell(w, 5, s(text), border=0)
        used_h = self.get_y() - start_y

        # volta e desenha a caixa com altura max(min_h, used_h+4)
        box_h = max(min_h, used_h + 4)
        self.set_xy(x, y)
        self.rect(x, y, w, box_h)

        # texto dentro da caixa
        self.set_xy(x + 1.5, y + 1.5)
        self.multi_cell(w - 3, 5, s(text), border=0)

        # posiciona abaixo
        self.set_xy(x, y + box_h + 2)

    def signature_block(self, label_left, label_right=None):
        """Bloco de assinatura com linha e (opcional) data."""
        total_w = self.w - self.l_margin - self.r_margin
        if label_right is None:
            # linha única
            self.ln(3)
            self.cell(total_w, 6, " " , ln=1, border=0)
            self.cell(total_w, 6, "_______________________________", ln=1, align="L")
            self.set_font(self.font_regular, "", 10)
            self.cell(total_w, 6, label_left, ln=1, align="L")
        else:
            # duas colunas (Assinatura / Data)
            left_w = total_w * 0.7
            right_w = total_w - left_w
            self.ln(2)
            self.set_font(self.font_regular, "", 10)
            self.cell(left_w, 6, "_______________________________", ln=0, align="L")
            self.cell(right_w, 6, "____/____/________", ln=1, align="R")
            self.cell(left_w, 6, label_left, ln=0, align="L")
            self.cell(right_w, 6, label_right, ln=1, align="R")

# ----------------------------
# CONEXÃO PLANILHA
# ----------------------------
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0)
    df.columns = [str(c).strip() for c in df.columns]
except Exception as e:
    st.error(f"Erro na conexão com a planilha: {e}")
    st.stop()

# ----------------------------
# MAPEAMENTO DE COLUNAS (PLANILHA)
# ----------------------------
COL_NOME = "Nome do Estudante"
COL_RESP = "Nome do Pai/Mãe ou responsável"
COL_OBS = "Obs."  # se existir na planilha
COL_TEL = "Telefone para contato"
COL_NASC = "Data do Nascimento"
COL_IDADE = "Idade"
COL_CURSO = "Curso"
COL_HIST = "(02) Histórico"
COL_NECESSIDADE = "(03) Necessidades Educacionais Específicas"
COL_HAB = "(04) Conhecimentos e Habilidades"
COL_DIF = "(05) Dificuldades Apresentadas"
COL_ADAPT = "(06) Adaptações Razoáveis e/ou Acessibilidades"

required = [COL_NOME]
missing = [c for c in required if c not in df.columns]
if missing:
    st.error(f"Coluna obrigatória ausente na planilha: {missing}")
    st.stop()

# ----------------------------
# UI: SELEÇÃO DO ALUNO
# ----------------------------
aluno_nome = st.selectbox("Selecione o Estudante:", ["Selecione..."] + df[COL_NOME].astype(str).tolist())

if aluno_nome == "Selecione...":
    st.info("Selecione um estudante para preencher o PEI.")
    st.stop()

aluno_row = df[df[COL_NOME].astype(str) == str(aluno_nome)].iloc[0]
aluno = aluno_row.to_dict()

st.subheader("📝 Preenchimento do Plano")

# (01) Dados pessoais adicionais
c1, c2, c3 = st.columns(3)
with c1:
    docente_input = st.text_input("Docente:", value="")
with c2:
    materia_input = st.text_input("Componente Curricular:", value="")
with c3:
    obs_input = st.text_input("Obs. (responsável):", value=s(aluno.get(COL_OBS, "")))

# Histórico editável (02)
hist_original = s(aluno.get(COL_HIST, ""))
texto_historico = st.text_area("(02) Histórico (Edite se necessário):", value=hist_original, height=120)

# (07)–(11) campos separados
st.markdown("### Desenvolvimento pedagógico (07)–(11)")
conteudo_input = st.text_area("(08) Conteúdos Programáticos:", height=100)

colA, colB = st.columns(2)
with colA:
    objetivos_07 = st.text_area("(07) Objetivos Específicos:", height=120)
    metodologia_09 = st.text_area("(09) Metodologia:", height=120)
with colB:
    avaliacao_10 = st.text_area("(10) Avaliação:", height=120)
    resultados_11 = st.text_area("(11) Resultados Esperados:", height=120)

# IA para sugerir (07, 09, 10, 11)
if st.button("🚀 Gerar Sugestões (IA) para (07), (09), (10) e (11)"):
    if not materia_input or not conteudo_input:
        st.warning("Preencha pelo menos 'Componente Curricular' e '(08) Conteúdos Programáticos' para a IA sugerir.")
    else:
        prompt = f"""
Você é um especialista em educação inclusiva e PEI (Plano Educacional Individualizado) no padrão de formulários do IFMT.
Gere sugestões OBJETIVAS e PRÁTICAS para os itens do PEI abaixo, em PT-BR, com bullets curtos e aplicáveis em sala.

Estudante: {s(aluno.get(COL_NOME))}
Componente Curricular: {materia_input}
Curso: {s(aluno.get(COL_CURSO))}
Necessidades educacionais específicas (03): {s(aluno.get(COL_NECESSIDADE))}
Conhecimentos/Habilidades (04): {s(aluno.get(COL_HAB))}
Dificuldades (05): {s(aluno.get(COL_DIF))}
Adaptações/Acessibilidades (06): {s(aluno.get(COL_ADAPT))}
Conteúdos programáticos (08): {conteudo_input}

Retorne no formato:
(07) ...
(09) ...
(10) ...
(11) ...
"""
        ia_txt = call_maritalk(prompt)
        st.session_state["ia_sugestoes_raw"] = ia_txt

# preencher campos a partir do retorno da IA (heurística simples)
if "ia_sugestoes_raw" in st.session_state:
    st.text_area("📌 Sugestões brutas da IA (referência):", value=st.session_state["ia_sugestoes_raw"], height=180)

# Bibliografias (12, 13)
b1, b2 = st.columns(2)
with b1:
    bib_b = st.text_input("(12) Bibliografia Básica:", value="Conforme o PPC do curso.")
with b2:
    bib_c = st.text_input("(13) Bibliografia Complementar:", value="Materiais adaptados e recursos digitais.")

# ----------------------------
# GERAR PDF
# ----------------------------
if st.button("📄 Finalizar e Gerar PDF (Padrão Anexo II)"):
    pdf = PEI_PDF()
    pdf.add_page()

    # (01) DADOS PESSOAIS (formato do anexo)
    pdf.section_bar("(01) DADOS PESSOAIS")
    pdf.field_line("Nome do Estudante", aluno.get(COL_NOME, ""))
    pdf.field_two_cols("Nome do Pai/Mãe ou responsável", aluno.get(COL_RESP, ""), "Obs.", obs_input)
    pdf.field_two_cols("Telefone para contato", aluno.get(COL_TEL, ""), "Data do Nascimento", aluno.get(COL_NASC, ""))
    pdf.field_two_cols("Idade", aluno.get(COL_IDADE, ""), "Curso", aluno.get(COL_CURSO, ""))
    pdf.field_two_cols("Componente Curricular", materia_input, "Docente", docente_input)

    # (02) HISTÓRICO
    pdf.section_bar("(02) HISTÓRICO (ANTERIOR, EM INSTITUIÇÃO DE ORIGEM ATÉ A ATUALIDADE)")
    pdf.big_box(texto_historico, min_h=30)

    # (03)
    pdf.section_bar("(03) NECESSIDADES EDUCACIONAIS ESPECÍFICAS")
    pdf.big_box(aluno.get(COL_NECESSIDADE, ""), min_h=22)

    # (04)
    pdf.section_bar("(04) CONHECIMENTOS, HABILIDADES, CAPACIDADES, INTERESSES, NECESSIDADES")
    pdf.big_box(aluno.get(COL_HAB, ""), min_h=22)

    # (05)
    pdf.section_bar("(05) DIFICULDADES APRESENTADAS")
    pdf.big_box(aluno.get(COL_DIF, ""), min_h=22)

    # (06)
    pdf.section_bar("(06) ADAPTAÇÕES RAZOÁVEIS E/OU ACESSIBILIDADES CURRICULARES")
    pdf.big_box(aluno.get(COL_ADAPT, ""), min_h=22)

    # (07)
    pdf.section_bar("(07) OBJETIVOS ESPECÍFICOS")
    pdf.big_box(objetivos_07, min_h=20)

    # (08)
    pdf.section_bar("(08) CONTEÚDOS PROGRAMÁTICOS")
    pdf.big_box(conteudo_input, min_h=20)

    # (09)
    pdf.section_bar("(09) METODOLOGIA")
    pdf.big_box(metodologia_09, min_h=20)

    # (10)
    pdf.section_bar("(10) AVALIAÇÃO")
    pdf.big_box(avaliacao_10, min_h=20)

    # (11)
    pdf.section_bar("(11) RESULTADOS ESPERADOS")
    pdf.big_box(resultados_11, min_h=20)

    # (12)
    pdf.section_bar("(12) BIBLIOGRAFIA BÁSICA")
    pdf.big_box(bib_b, min_h=18)

    # (13)
    pdf.section_bar("(13) BIBLIOGRAFIA COMPLEMENTAR")
    pdf.big_box(bib_c, min_h=18)

    # (14) ASSINATURAS (como no anexo: docente, coordenação, depto + datas)
    pdf.section_bar("(14) ASSINATURAS")
    pdf.signature_block("Assinatura do Docente:", "Data:")
    pdf.signature_block("Assinatura da Coordenação de Curso:", "Data:")
    pdf.signature_block("Assinatura do Departamento de Ensino:", "Data:")

    # bytes corretos para download
    pdf_str = pdf.output(dest="S")
    try:
        pdf_bytes = pdf_str.encode("latin-1")
    except Exception:
        # fpdf2 às vezes já retorna bytes
        pdf_bytes = pdf_str if isinstance(pdf_str, (bytes, bytearray)) else bytes(pdf_str, "utf-8", errors="ignore")

    st.download_button(
        label="📥 Baixar PDF Finalizado",
        data=pdf_bytes,
        file_name=f"PEI_{aluno_nome}.pdf",
        mime="application/pdf"
    )

