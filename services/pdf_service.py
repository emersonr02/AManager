"""
PDFService — gera a Ordem de Produção em PDF, pronta a imprimir e a
acompanhar a peça no laboratório físico. Inclui um QR code que aponta
para um identificador único da produção (para consulta rápida futura).
"""
import io
import os
from datetime import datetime

from fpdf import FPDF
import qrcode

from config.paths import BASE_DIR


_AZUL_CEIIA   = (10, 126, 140)   # theme.ACCENT
_CINZA_TEXTO  = (60, 60, 60)
_CINZA_CLARO  = (235, 238, 240)


class PDFService:

    @staticmethod
    def _qr_para_bytes(texto: str) -> bytes:
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(texto)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    @staticmethod
    def gerar_ordem_producao(producao: dict, pedidos_vinculados: list,
                             id_para_nome_maquina: dict, caminho_saida: str) -> str:
        """Gera o PDF da ordem de produção e devolve o caminho do ficheiro criado."""
        from services.producao_service import ProducaoService

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()

        # ── Cabeçalho ────────────────────────────────────────────────────
        pdf.set_fill_color(*_AZUL_CEIIA)
        pdf.rect(0, 0, 210, 28, style="F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_xy(15, 8)
        pdf.cell(0, 10, "ORDEM DE PRODUÇÃO", ln=1)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_xy(15, 18)
        codigo = ProducaoService.formatar_codigo(producao.get("id"))
        pdf.cell(0, 6, f"{codigo}  |  i3D MES · CEiiA", ln=1)

        # QR code no canto superior direito — usa ficheiro temporário do SO
        # (com try/finally) para nunca deixar lixo na pasta da app, mesmo
        # que a geração da imagem falhe a meio.
        import tempfile
        qr_bytes = PDFService._qr_para_bytes(f"AManager:PRD:{producao.get('id')}")
        fd, qr_path = tempfile.mkstemp(suffix=".png")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(qr_bytes)
            pdf.image(qr_path, x=172, y=4, w=22, h=22)
        finally:
            os.remove(qr_path)

        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.ln(18)

        # ── Bloco de identificação ──────────────────────────────────────
        maquina = ProducaoService.normalizar_maquina(producao, id_para_nome_maquina)
        tempo_est = ProducaoService.normalizar_tempo(producao)

        campos = [
            ("Máquina",          maquina),
            ("Tecnologia",       producao.get("tecnologia", "")),
            ("Data de Início",   producao.get("data_inicio", "")),
            ("Tempo Estimado",   tempo_est),
            ("Operador",         producao.get("operador") or producao.get("responsavel", "")),
        ]
        PDFService._secao_titulo(pdf, "Identificação")
        PDFService._tabela_campos(pdf, campos)

        # ── Projeto(s) e requerente(s) ────────────────────────────────────
        if pedidos_vinculados:
            PDFService._secao_titulo(pdf, "Pedido(s) Associado(s)")
            for p in pedidos_vinculados:
                proj = f"{p.get('nr_projeto','')} - {p.get('nome_projeto','')}".strip(" -")
                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(0, 6, f"- {proj}", ln=1)
                pdf.set_font("Helvetica", "", 9)
                pdf.cell(0, 5, f"   Requerente: {p.get('requerente_email','N/A')}", ln=1)
                for peca in p.get("pecas", []):
                    pdf.cell(0, 5,
                        f"   - {peca.get('pn','')} | {peca.get('material','')} | Qtd: {peca.get('qtd','')}",
                        ln=1)
                pdf.ln(2)
        elif producao.get("nr_projeto"):
            PDFService._secao_titulo(pdf, "Projeto")
            PDFService._tabela_campos(pdf, [
                ("Projeto",  producao.get("nr_projeto", "")),
                ("Material", producao.get("material", "")),
            ])

        # ── Parâmetros específicos SLS ──────────────────────────────────
        if producao.get("tecnologia") == "SLS":
            PDFService._secao_titulo(pdf, "Parâmetros SLS")
            PDFService._tabela_campos(pdf, [
                ("Altura da Cuba (mm)", str(producao.get("altura_cuba", ""))),
                ("% Pó Novo",           str(producao.get("percentagem_po_novo", ""))),
                ("Lote de Pó",          producao.get("lote_po", "")),
            ])

        # ── Checklist de segurança ────────────────────────────────────────
        checklist = producao.get("checklist_seguranca", {})
        if checklist:
            PDFService._secao_titulo(pdf, "Checklist de Segurança")
            for chave, valor in checklist.items():
                marca = "[x]" if valor else "[ ]"
                pdf.set_font("Helvetica", "", 10)
                pdf.cell(0, 6, f"{marca}  {chave.replace('_', ' ').title()}", ln=1)

        # ── Não-conformidade e ações corretivas (loop CAPA) ───────────────
        nc_cod = producao.get("nc_codigo", "")
        if nc_cod:
            from services.nc_service import NCService
            PDFService._secao_titulo(pdf, "Não-Conformidade e Ações Corretivas")
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(50, 6, "Código NC:", border=0)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 6, f"{nc_cod} - {NCService.obter_descricao(nc_cod)}", ln=1)

            acoes_aplicadas = producao.get("acoes_aplicadas", [])
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, "Ações corretivas aplicadas:", ln=1)
            pdf.set_font("Helvetica", "", 9)
            if acoes_aplicadas:
                for act_cod in acoes_aplicadas:
                    pdf.cell(0, 5, f"  [x] {NCService.obter_nome_acao(act_cod)}", ln=1)
            else:
                pdf.set_text_color(200, 100, 30)
                pdf.cell(0, 5, "  Nenhuma ação corretiva confirmada como aplicada.", ln=1)
                pdf.set_text_color(*_CINZA_TEXTO)

            notas = producao.get("notas_acao_corretiva", "")
            if notas:
                pdf.set_font("Helvetica", "I", 8)
                pdf.multi_cell(0, 5, f"Notas: {notas}")

        # ── Espaço para assinatura / verificação física ──────────────────
        pdf.ln(6)
        PDFService._secao_titulo(pdf, "Verificação (preencher no laboratório)")
        y_linha = pdf.get_y() + 14
        pdf.set_draw_color(180, 180, 180)
        pdf.line(15, y_linha, 90, y_linha)
        pdf.line(120, y_linha, 195, y_linha)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_xy(15, y_linha + 1)
        pdf.cell(75, 5, "Assinatura do Operador", align="C")
        pdf.set_xy(120, y_linha + 1)
        pdf.cell(75, 5, "Data / Hora de Conclusão", align="C")

        # ── Rodapé ──────────────────────────────────────────────────────
        pdf.set_y(-15)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(140, 140, 140)
        pdf.cell(0, 10,
            f"Gerado por AManager MES · {datetime.now().strftime('%Y-%m-%d %H:%M')} · CEiiA i3D",
            align="C")

        pdf.output(caminho_saida)
        return caminho_saida

    @staticmethod
    def _secao_titulo(pdf: FPDF, texto: str):
        pdf.ln(4)
        pdf.set_fill_color(*_CINZA_CLARO)
        pdf.set_text_color(*_AZUL_CEIIA)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"  {texto}", ln=1, fill=True)
        pdf.set_text_color(*_CINZA_TEXTO)
        pdf.ln(1)

    @staticmethod
    def _tabela_campos(pdf: FPDF, campos: list):
        for label, valor in campos:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(50, 6, f"{label}:", border=0)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 6, str(valor) if valor else "N/A", ln=1)
