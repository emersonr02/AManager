import csv
import os
from datetime import datetime

from config.paths import ARQUIVO_MAQUINAS
from database.json_manager import JSONManager

# ─────────────────────────────────────────────
# CABEÇALHO PRINCIPAL
# ─────────────────────────────────────────────
CABECALHO_AUDITORIA = [
    "Nº PRODUÇÃO", "ESTADO", "TECNOLOGIA", "MÁQUINA",
    "OPERADOR (INÍCIO)", "DATA INÍCIO", "VERIFICADO POR (FECHO)", "DATA FECHO",
    "DURAÇÃO JOB (h)",
    "PEDIDOS VINCULADOS", "PROJETOS", "REQUERENTES", "MATERIAL",
    "TEMPO ESTIMADO", "TEMPO REAL", "Δ TEMPO (est→real)",
    "QUANTIDADE ESTIMADA", "QUANTIDADE REAL",
    "QA GERAL", "INSPEÇÃO VISUAL", "CONTROLO DIMENSIONAL", "CONFORMIDADE",
    "CHECKLIST SEGURANÇA", "CHECKLIST COMPLETO",
    "CÓDIGO NC", "DESCRIÇÃO NC", "AÇÕES CORRETIVAS SUGERIDAS",
    "AÇÕES CORRETIVAS APLICADAS", "NOTAS DA CORREÇÃO",
    "ALTURA CUBA (SLS)", "% PÓ NOVO (SLS)", "LOTE PÓ (SLS)",
]


class ExportService:

    # ─────────────────────────────────────────────
    # HELPERS INTERNOS
    # ─────────────────────────────────────────────

    @staticmethod
    def _id_para_nome_maquina() -> dict:
        """Resolve id_maquina legacy (ex: 'X1C-2') → nome completo (ex: 'Bambu Lab X1C #2')."""
        maquinas_db = JSONManager.carregar(ARQUIVO_MAQUINAS) if os.path.exists(ARQUIVO_MAQUINAS) else []
        return {m.get("id"): m.get("nome") for m in maquinas_db
                if isinstance(m, dict) and m.get("id") and m.get("nome")}

    @staticmethod
    def _pedidos_vinculados(producao: dict, pedidos_por_id: dict) -> list:
        return [pedidos_por_id[v] for v in producao.get("pedidos_vinculados", [])
                if v in pedidos_por_id]

    @staticmethod
    def _materiais_de_pedidos(pedidos: list) -> str:
        mats = sorted({peca.get("material") for p in pedidos
                       for peca in p.get("pecas", []) if peca.get("material")})
        return " | ".join(mats) if mats else ""

    @staticmethod
    def _resumir_checklist(checklist: dict) -> tuple[str, str]:
        if not checklist:
            return "", ""
        detalhe = "; ".join(f"{k}: {'OK' if v else 'NOK'}" for k, v in checklist.items())
        completo = "Sim" if all(checklist.values()) else "Não"
        return detalhe, completo

    @staticmethod
    def _hhmm_para_horas(hhmm: str) -> float:
        """Delega para ProducaoService.converter_para_horas que suporta todos
        os formatos legacy: 'HH:MM', 'H:MM:SS', 'N days, H:MM:SS'."""
        from services.producao_service import ProducaoService
        return ProducaoService.converter_para_horas(str(hhmm))

    @staticmethod
    def _horas_para_hhmm(horas: float) -> str:
        """Converte float de horas para 'HH:MM'."""
        h = int(horas)
        m = int(round((horas - h) * 60))
        if m == 60:
            h += 1
            m = 0
        return f"{h:02d}:{m:02d}"

    @staticmethod
    def _delta_tempo(estimado: str, real: str) -> str:
        """
        Devolve a diferença real − estimado em formato ±HH:MM.
        '+' significa que demorou mais do que o previsto.
        '-' significa que foi mais rápido.
        """
        h_est = ExportService._hhmm_para_horas(estimado)
        h_real = ExportService._hhmm_para_horas(real)
        if h_est == 0.0 and h_real == 0.0:
            return ""
        delta = h_real - h_est
        sinal = "+" if delta >= 0 else "-"
        return f"{sinal}{ExportService._horas_para_hhmm(abs(delta))}"

    @staticmethod
    def _duracao_job(data_inicio: str, data_fecho: str) -> str:
        """Calcula a duração real (data_fecho − data_inicio) em HH:MM."""
        fmts = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]
        def parse(s):
            for fmt in fmts:
                try:
                    return datetime.strptime(s.strip(), fmt)
                except (ValueError, AttributeError):
                    continue
            return None
        ini = parse(data_inicio)
        fim = parse(data_fecho)
        if not ini or not fim or fim < ini:
            return ""
        delta_h = (fim - ini).total_seconds() / 3600
        return ExportService._horas_para_hhmm(delta_h)

    @staticmethod
    def _obter_maquina(producao: dict, id_para_nome: dict) -> str:
        """Delega para ProducaoService.normalizar_maquina (inclui mapeamentos legacy)."""
        from services.producao_service import ProducaoService
        return ProducaoService.normalizar_maquina(producao, id_para_nome)

    @staticmethod
    def _obter_operador(producao: dict) -> str:
        """Compatibilidade legacy: 'responsavel' era o nome antigo de 'operador'."""
        return producao.get("operador") or producao.get("responsavel", "")

    @staticmethod
    def _obter_tempo_estimado(producao: dict) -> str:
        """Tempo estimado normalizado para HH:MM (suporta todos os formatos legacy)."""
        from services.producao_service import ProducaoService
        raw = producao.get("tempo_estimado") or producao.get("hora_maquina", "")
        if not raw:
            return ""
        return ProducaoService.converter_para_string(ProducaoService.converter_para_horas(str(raw)))

    @staticmethod
    def _obter_quantidade_estimada(producao: dict) -> str:
        """Compatibilidade legacy: delega para estimar_quantidade com fallback."""
        from services.producao_service import ProducaoService
        est = ProducaoService.estimar_quantidade(producao)
        if not est:
            # Legacy: campo 'quantidade' direto
            qtd = producao.get("quantidade")
            est = str(qtd) if qtd is not None else ""
        return est

    @staticmethod
    def _obter_quantidade_real(producao: dict) -> str:
        """Compatibilidade legacy."""
        return str(producao.get("quantidade_real") or producao.get("quantidade", ""))

    @staticmethod
    def _qa_geral(producao: dict) -> str:
        """Verifica se os 3 controlos de qualidade passaram (estrutura nova e legado flat)."""
        qa = producao.get("controlo_qualidade", {})
        if qa:
            passou = (qa.get("inspecao_visual") and
                      qa.get("controlo_dimensional") and
                      qa.get("conformidade"))
        else:
            # Legacy: campos planos
            passou = (producao.get("inspecao_visual") and
                      producao.get("controlo_dimensional") and
                      producao.get("conformidade_peca"))
        if passou is None:
            return ""
        return "Sim" if passou else "Não"

    @staticmethod
    def _qa_campo(producao: dict, campo_novo: str, campo_legacy: str) -> str:
        qa = producao.get("controlo_qualidade", {})
        val = qa.get(campo_novo) if qa else producao.get(campo_legacy)
        if val is None:
            return ""
        return "Sim" if val else "Não"

    # ─────────────────────────────────────────────
    # FORMATAÇÃO DE LINHA
    # ─────────────────────────────────────────────

    @staticmethod
    def _formatar_linha_producao(producao: dict, pedidos_por_id: dict, id_para_nome: dict) -> list:
        from services.producao_service import ProducaoService
        from services.pedido_service import PedidoService
        from services.nc_service import NCService

        # Campos base com compatibilidade legacy
        maquina      = ExportService._obter_maquina(producao, id_para_nome)
        operador     = ExportService._obter_operador(producao)
        tempo_est    = ExportService._obter_tempo_estimado(producao)
        tempo_real   = producao.get("tempo_real", "")
        qtd_est      = ExportService._obter_quantidade_estimada(producao)
        qtd_real     = ExportService._obter_quantidade_real(producao)
        data_inicio  = producao.get("data_inicio", "")
        data_fecho   = producao.get("data_fecho", "")

        # Pedidos/Projeto/Material — novo sistema vs legado
        vinculos_raw = producao.get("pedidos_vinculados", [])
        if isinstance(vinculos_raw, list) and vinculos_raw:
            pedidos     = ExportService._pedidos_vinculados(producao, pedidos_por_id)
            pedidos_fmt = " | ".join(PedidoService.formatar_codigo(v) for v in vinculos_raw)
            projetos    = sorted({
                f"{p.get('nr_projeto', '')} - {p.get('nome_projeto', '')}".strip(" -")
                for p in pedidos
            })
            requerentes = sorted({p.get("requerente_email", "") for p in pedidos if p.get("requerente_email")})
            material    = ExportService._materiais_de_pedidos(pedidos) or "N/A"
        else:
            # Legado: campos diretos
            pedidos_fmt = "N/A"
            nr_proj     = producao.get("nr_projeto", "")
            projetos    = [nr_proj] if nr_proj else []
            requerentes = [operador] if operador else []
            material    = producao.get("material", "N/A")

        # NC
        nc_cod   = producao.get("nc_codigo", "")
        nc_desc  = NCService.obter_descricao(nc_cod) if nc_cod else ""
        acoes    = "; ".join(a.get("acao", "") for a in NCService.obter_acoes_por_cod(nc_cod)) if nc_cod else ""
        acoes_aplicadas = NCService.formatar_acoes_aplicadas(producao.get("acoes_aplicadas", []))
        notas_correcao  = producao.get("notas_acao_corretiva", "")

        # Checklist
        checklist_txt, checklist_ok = ExportService._resumir_checklist(producao.get("checklist_seguranca", {}))

        return [
            ProducaoService.formatar_codigo(producao.get("id")),
            producao.get("estado", ""),
            producao.get("tecnologia", ""),
            maquina,
            operador,
            data_inicio,
            producao.get("verificado_por", ""),
            data_fecho,
            ExportService._duracao_job(data_inicio, data_fecho),
            pedidos_fmt,
            " | ".join(projetos),
            " | ".join(requerentes),
            material,
            tempo_est,
            tempo_real,
            ExportService._delta_tempo(tempo_est, tempo_real),
            qtd_est,
            qtd_real,
            ExportService._qa_geral(producao),
            ExportService._qa_campo(producao, "inspecao_visual",      "inspecao_visual"),
            ExportService._qa_campo(producao, "controlo_dimensional", "controlo_dimensional"),
            ExportService._qa_campo(producao, "conformidade",         "conformidade_peca"),
            checklist_txt,
            checklist_ok,
            nc_cod,
            nc_desc,
            acoes,
            acoes_aplicadas,
            notas_correcao,
            producao.get("altura_cuba", ""),
            producao.get("percentagem_po_novo", ""),
            producao.get("lote_po", ""),
        ]

    # ─────────────────────────────────────────────
    # EXPORT PRINCIPAL
    # ─────────────────────────────────────────────

    @staticmethod
    def exportar_historico_csv(caminho_salvar: str, producoes: list, pedidos_db: list) -> bool:
        """
        Gera o CSV de auditoria completo com:
          1. Metadados de exportação
          2. Tabela principal (uma linha por produção)
          3. KPIs gerais
          4. Breakdown por estado
          5. Análise de qualidade (QA)
          6. Pareto de não-conformidades
          7. Resumo por projeto
          8. Resumo por material
          9. Resumo por máquina
        Retorna True se bem sucedido, False caso contrário.
        """
        from services.producao_service import ProducaoService
        from services.nc_service import NCService

        id_para_nome   = ExportService._id_para_nome_maquina()
        pedidos_por_id = {p.get("id"): p for p in pedidos_db}

        # ── Acumuladores para os resumos ──────────────────
        contagem_estado  = {}
        consumo_material = {}   # material → {qtd, n_prod}
        horas_maquina    = {}   # maquina  → {horas, n_prod, n_ok}
        horas_projeto    = {}   # projeto  → {horas, qtd, n_prod, n_ok}
        nc_pareto        = {}   # nc_cod   → {"total": n, "com_acao": n}
        qa_counts        = {"inspecao_visual": [0, 0],       # [ok, total]
                            "controlo_dimensional": [0, 0],
                            "conformidade": [0, 0]}

        total_horas_global = 0.0
        total_qtd_global   = 0.0

        # ── Pré-processamento ──────────────────────────────
        for prod in producoes:
            estado   = prod.get("estado", "")
            if estado == "Falha":       estado = "Cancelada"
            if estado == "A Imprimir":  estado = "Em Andamento"
            contagem_estado[estado] = contagem_estado.get(estado, 0) + 1

            maquina    = ExportService._obter_maquina(prod, id_para_nome)
            tempo_est  = ExportService._obter_tempo_estimado(prod)
            tempo_real = prod.get("tempo_real", "")
            horas      = ExportService._hhmm_para_horas(tempo_real or tempo_est)
            total_horas_global += horas
            n_ok = 1 if estado == "Concluída" else 0

            # Projeto(s)
            vinculos_raw = prod.get("pedidos_vinculados", [])
            if isinstance(vinculos_raw, list) and vinculos_raw:
                pedidos_prod = ExportService._pedidos_vinculados(prod, pedidos_por_id)
                projetos_prod = sorted({
                    f"{p.get('nr_projeto', '')} - {p.get('nome_projeto', '')}".strip(" -")
                    for p in pedidos_prod
                }) or ["N/A"]
                mat = ExportService._materiais_de_pedidos(pedidos_prod) or "N/A"
            else:
                projetos_prod = [prod.get("nr_projeto", "N/A") or "N/A"]
                mat = prod.get("material", "N/A")

            try:
                qtd = float(str(prod.get("quantidade_real") or
                                prod.get("quantidade_consumida") or
                                prod.get("quantidade") or 0
                                ).replace(",", "."))
            except (ValueError, TypeError):
                qtd = 0.0
            total_qtd_global += qtd

            # Material
            acc = consumo_material.setdefault(mat, {"qtd": 0.0, "n_prod": 0})
            acc["qtd"] += qtd
            acc["n_prod"] += 1

            # Máquina
            acc_m = horas_maquina.setdefault(maquina or "N/A", {"horas": 0.0, "n_prod": 0, "n_ok": 0})
            acc_m["horas"]  += horas
            acc_m["n_prod"] += 1
            acc_m["n_ok"]   += n_ok

            # Projeto
            for proj in projetos_prod:
                acc_p = horas_projeto.setdefault(proj, {"horas": 0.0, "qtd": 0.0, "n_prod": 0, "n_ok": 0})
                acc_p["horas"]  += horas
                acc_p["qtd"]    += qtd
                acc_p["n_prod"] += 1
                acc_p["n_ok"]   += n_ok

            # NC Pareto — regista também se o loop CAPA foi fechado
            # (pelo menos uma ação corretiva confirmada como aplicada)
            nc_cod = prod.get("nc_codigo", "")
            if nc_cod:
                acc_nc = nc_pareto.setdefault(nc_cod, {"total": 0, "com_acao": 0})
                acc_nc["total"] += 1
                if prod.get("acoes_aplicadas"):
                    acc_nc["com_acao"] += 1

            # QA
            qa = prod.get("controlo_qualidade", {})
            for chave_novo, chave_leg, chave_acc in [
                ("inspecao_visual",      "inspecao_visual",      "inspecao_visual"),
                ("controlo_dimensional", "controlo_dimensional", "controlo_dimensional"),
                ("conformidade",         "conformidade_peca",    "conformidade"),
            ]:
                val = qa.get(chave_novo) if qa else prod.get(chave_leg)
                if val is not None:
                    qa_counts[chave_acc][1] += 1
                    if val:
                        qa_counts[chave_acc][0] += 1

        total_prod    = len(producoes)
        n_concluidas  = contagem_estado.get("Concluída", 0) + contagem_estado.get("Entregue", 0)
        n_canceladas  = contagem_estado.get("Cancelada", 0)
        taxa_sucesso  = (n_concluidas / total_prod * 100) if total_prod else 0.0

        # ── Escrita do CSV ─────────────────────────────────
        try:
            with open(caminho_salvar, mode="w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")

                def sep(titulo=""):
                    w.writerow([])
                    if titulo:
                        w.writerow([f"══ {titulo} ══"])

                # ── 1. METADADOS ──────────────────────────────
                w.writerow(["RELATÓRIO DE AUDITORIA DE PRODUÇÃO — AManager i3D"])
                w.writerow(["Exportado em",   datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                w.writerow(["Total de registos exportados", total_prod])
                w.writerow([])

                # ── 2. TABELA PRINCIPAL ───────────────────────
                sep("DETALHE DE PRODUÇÕES")
                w.writerow(CABECALHO_AUDITORIA)
                for prod in producoes:
                    w.writerow(ExportService._formatar_linha_producao(prod, pedidos_por_id, id_para_nome))

                # ── 3. KPIs GERAIS ────────────────────────────
                sep("KPIs GERAIS")
                w.writerow(["INDICADOR", "VALOR"])
                w.writerow(["Total de produções",       total_prod])
                w.writerow(["Concluídas / Entregues",   n_concluidas])
                w.writerow(["Canceladas",                n_canceladas])
                w.writerow(["Em Andamento",              contagem_estado.get("Em Andamento", 0)])
                w.writerow(["Taxa de sucesso",           f"{taxa_sucesso:.1f}%"])
                w.writerow(["Total horas máquina",       ExportService._horas_para_hhmm(total_horas_global)])
                w.writerow(["Total material consumido (g)", f"{total_qtd_global:.2f}"])
                avg_h = total_horas_global / total_prod if total_prod else 0
                w.writerow(["Média tempo/produção",      ExportService._horas_para_hhmm(avg_h)])

                # ── 4. BREAKDOWN POR ESTADO ───────────────────
                sep("BREAKDOWN POR ESTADO")
                w.writerow(["ESTADO", "QTD", "% DO TOTAL"])
                for estado, cnt in sorted(contagem_estado.items(), key=lambda x: -x[1]):
                    pct = cnt / total_prod * 100 if total_prod else 0
                    w.writerow([estado, cnt, f"{pct:.1f}%"])

                # ── 5. ANÁLISE DE QUALIDADE (QA) ──────────────
                sep("ANÁLISE DE QUALIDADE")
                w.writerow(["VERIFICAÇÃO", "APROVAÇÕES", "REPROVAÇÕES", "TOTAL", "TAXA OK"])
                labels = {
                    "inspecao_visual":      "Inspeção Visual",
                    "controlo_dimensional": "Controlo Dimensional",
                    "conformidade":         "Conformidade da Peça",
                }
                for chave, label in labels.items():
                    ok, total = qa_counts[chave]
                    nok = total - ok
                    taxa = ok / total * 100 if total else 0
                    w.writerow([label, ok, nok, total, f"{taxa:.1f}%"])

                # ── 6. PARETO DE NÃO-CONFORMIDADES ───────────
                sep("PARETO DE NÃO-CONFORMIDADES")
                if nc_pareto:
                    w.writerow(["CÓDIGO NC", "DESCRIÇÃO", "Nº OCORRÊNCIAS", "% DAS CANCELADAS", "TAXA DE FECHO (CAPA)"])
                    for nc_cod, dados in sorted(nc_pareto.items(), key=lambda x: -x[1]["total"]):
                        desc = NCService.obter_descricao(nc_cod)
                        cnt = dados["total"]
                        pct = cnt / n_canceladas * 100 if n_canceladas else 0
                        taxa_fecho = dados["com_acao"] / cnt * 100 if cnt else 0
                        w.writerow([nc_cod, desc, cnt, f"{pct:.1f}%", f"{taxa_fecho:.0f}%"])
                else:
                    w.writerow(["Sem não-conformidades registadas no período exportado."])

                # ── 7. RESUMO POR PROJETO ─────────────────────
                sep("RESUMO POR PROJETO")
                w.writerow(["PROJETO", "HORAS MÁQUINA", "MATERIAL (g)", "Nº ORDENS", "TAXA SUCESSO"])
                for proj, acc in sorted(horas_projeto.items(), key=lambda x: -x[1]["horas"]):
                    taxa_p = acc["n_ok"] / acc["n_prod"] * 100 if acc["n_prod"] else 0
                    w.writerow([
                        proj,
                        ExportService._horas_para_hhmm(acc["horas"]),
                        f"{acc['qtd']:.2f}",
                        acc["n_prod"],
                        f"{taxa_p:.1f}%",
                    ])

                # ── 8. RESUMO POR MATERIAL ────────────────────
                sep("RESUMO POR MATERIAL")
                w.writerow(["MATERIAL", "QTD TOTAL (g)", "Nº PRODUÇÕES", "MÉDIA/PRODUÇÃO (g)"])
                for mat, acc in sorted(consumo_material.items(), key=lambda x: -x[1]["qtd"]):
                    media = acc["qtd"] / acc["n_prod"] if acc["n_prod"] else 0
                    w.writerow([mat, f"{acc['qtd']:.2f}", acc["n_prod"], f"{media:.2f}"])

                # ── 9. RESUMO POR MÁQUINA ─────────────────────
                sep("RESUMO POR MÁQUINA")
                w.writerow(["MÁQUINA", "HORAS TOTAIS", "Nº PRODUÇÕES", "TAXA SUCESSO"])
                for maq, acc in sorted(horas_maquina.items(), key=lambda x: -x[1]["horas"]):
                    taxa_m = acc["n_ok"] / acc["n_prod"] * 100 if acc["n_prod"] else 0
                    w.writerow([
                        maq,
                        ExportService._horas_para_hhmm(acc["horas"]),
                        acc["n_prod"],
                        f"{taxa_m:.1f}%",
                    ])

            return True
        except Exception as e:
            print(f"Erro na exportação CSV: {e}")
            return False
