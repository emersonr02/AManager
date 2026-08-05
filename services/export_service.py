import csv

CABECALHO_AUDITORIA = [
    "Nº PRODUÇÃO", "ESTADO", "TECNOLOGIA", "MÁQUINA",
    "OPERADOR (INÍCIO)", "DATA INÍCIO", "VERIFICADO POR (FECHO)", "DATA FECHO",
    "PEDIDOS VINCULADOS", "PROJETOS", "REQUERENTES", "MATERIAL",
    "TEMPO ESTIMADO", "TEMPO REAL", "QUANTIDADE ESTIMADA", "QUANTIDADE REAL",
    "CHECKLIST SEGURANÇA", "CHECKLIST COMPLETO",
    "INSPEÇÃO VISUAL", "CONTROLO DIMENSIONAL", "CONFORMIDADE",
    "CÓDIGO NC", "DESCRIÇÃO NC", "AÇÕES CORRETIVAS SUGERIDAS",
    "ALTURA CUBA (SLS)", "% PÓ NOVO (SLS)", "LOTE PÓ (SLS)",
]


class ExportService:

    @staticmethod
    def _pedidos_vinculados(producao: dict, pedidos_por_id: dict) -> list:
        return [pedidos_por_id[v] for v in producao.get("pedidos_vinculados", []) if v in pedidos_por_id]

    @staticmethod
    def _materiais(pedidos: list) -> str:
        materiais = sorted({peca.get("material") for p in pedidos for peca in p.get("pecas", []) if peca.get("material")})
        return " | ".join(materiais) if materiais else "N/A"

    @staticmethod
    def _resumir_checklist(checklist: dict) -> tuple:
        if not checklist:
            return "", ""
        detalhe = "; ".join(f"{chave}: {'OK' if ok else 'NOK'}" for chave, ok in checklist.items())
        completo = "Sim" if all(checklist.values()) else "Não"
        return detalhe, completo

    @staticmethod
    def _formatar_linha_producao(producao: dict, pedidos_por_id: dict) -> list:
        from services.producao_service import ProducaoService
        from services.pedido_service import PedidoService
        from services.nc_service import NCService

        pedidos = ExportService._pedidos_vinculados(producao, pedidos_por_id)
        pedidos_fmt = " | ".join(PedidoService.formatar_codigo(v) for v in producao.get("pedidos_vinculados", [])) or "N/A"
        projetos = sorted({f"{p.get('nr_projeto', '')} - {p.get('nome_projeto', '')}".strip(" -") for p in pedidos})
        requerentes = sorted({p.get("requerente_email", "") for p in pedidos if p.get("requerente_email")})

        qa = producao.get("controlo_qualidade", {})
        checklist_txt, checklist_ok = ExportService._resumir_checklist(producao.get("checklist_seguranca", {}))

        nc_cod = producao.get("nc_codigo", "")
        nc_desc = NCService.obter_descricao(nc_cod) if nc_cod else ""
        acoes_txt = "; ".join(a.get("acao", "") for a in NCService.obter_acoes_por_cod(nc_cod)) if nc_cod else ""

        return [
            ProducaoService.formatar_codigo(producao.get("id")),
            producao.get("estado", ""),
            producao.get("tecnologia", ""),
            producao.get("maquina", ""),
            producao.get("operador", ""),
            producao.get("data_inicio", ""),
            producao.get("verificado_por", ""),
            producao.get("data_fecho", ""),
            pedidos_fmt,
            " | ".join(projetos),
            " | ".join(requerentes),
            ExportService._materiais(pedidos),
            producao.get("tempo_estimado", ""),
            producao.get("tempo_real", ""),
            ProducaoService.estimar_quantidade(producao),
            producao.get("quantidade_real", ""),
            checklist_txt,
            checklist_ok,
            "Sim" if qa.get("inspecao_visual") else "Não",
            "Sim" if qa.get("controlo_dimensional") else "Não",
            "Sim" if qa.get("conformidade") else "Não",
            nc_cod,
            nc_desc,
            acoes_txt,
            producao.get("altura_cuba", ""),
            producao.get("percentagem_po_novo", ""),
            producao.get("lote_po", ""),
        ]

    @staticmethod
    def exportar_historico_csv(caminho_salvar: str, producoes: list, pedidos_db: list) -> bool:
        """
        Gera o CSV de auditoria: uma linha completa por produção — quem
        iniciou e quem verificou o fecho, pedidos/projetos/requerentes
        vinculados, checklist de segurança, controlo de qualidade e
        não-conformidade — seguida dos resumos de Pareto por material e
        por máquina.
        Retorna True se for bem sucedido, False caso contrário.
        """
        from services.producao_service import ProducaoService

        pedidos_por_id = {p.get("id"): p for p in pedidos_db}

        try:
            with open(caminho_salvar, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')

                writer.writerow(CABECALHO_AUDITORIA)

                consumo_materiais = {}
                horas_maquinas = {}

                for producao in producoes:
                    writer.writerow(ExportService._formatar_linha_producao(producao, pedidos_por_id))

                    pedidos = ExportService._pedidos_vinculados(producao, pedidos_por_id)
                    material_chave = ExportService._materiais(pedidos)
                    qtd_str = producao.get("quantidade_real") or ProducaoService.estimar_quantidade(producao)
                    try:
                        qtd = float(str(qtd_str).replace(",", "."))
                    except (ValueError, TypeError):
                        qtd = 0.0
                    consumo_materiais[material_chave] = consumo_materiais.get(material_chave, 0.0) + qtd

                    maquina = producao.get("maquina", "N/A")
                    tempo_str = producao.get("tempo_real") or producao.get("tempo_estimado", "00:00")
                    horas = ProducaoService.converter_para_horas(str(tempo_str))
                    horas_maquinas[maquina] = horas_maquinas.get(maquina, 0.0) + horas

                writer.writerow([])
                writer.writerow([])

                writer.writerow(["RESUMO POR MATERIAL", "QUANTIDADE TOTAL"])
                for mat, tot in consumo_materiais.items():
                    writer.writerow([mat, f"{tot:.2f}"])

                writer.writerow([])

                writer.writerow(["RESUMO POR MÁQUINA", "HORAS TOTAIS"])
                for maq, tot_h in horas_maquinas.items():
                    writer.writerow([maq, ProducaoService.converter_para_string(tot_h)])

            return True
        except Exception as e:
            print(f"Erro na exportação CSV: {e}")
            return False
