"""
ResumoDiarioService — agrega os dados do "resumo do dia" (produções,
não-conformidades, máquinas paradas) numa única fonte de verdade, usada
tanto pela janela que abre no arranque da app como pela exportação em PDF.

Também controla se o resumo já foi mostrado hoje nesta máquina, para não
interromper o operador em cada reinício da app no mesmo dia.
"""
import os
from datetime import datetime


class ResumoDiarioService:

    # Marcador local (não vive na pasta de dados partilhada em rede —
    # cada PC/operador tem o seu próprio "já vi o resumo de hoje").
    _MARCADOR_DIR = os.path.join(os.path.expanduser("~"), ".amanager")

    @staticmethod
    def coletar(data_referencia: str = None) -> dict:
        """Recolhe e agrega todos os dados necessários para o resumo do
        dia. Devolve um dicionário com listas de produções e máquinas —
        tanto a janela como o PDF renderizam a partir deste mesmo dado,
        para nunca divergirem entre si."""
        from services.producao_service import ProducaoService
        from services.maquina_service import MaquinaService

        data_ref = data_referencia or datetime.now().strftime("%Y-%m-%d")

        id_para_nome = MaquinaService.obter_lookup_id_nome()
        todas_producoes = ProducaoService.obter_todos()
        producoes_hoje = [
            p for p in todas_producoes
            if str(p.get("data_inicio", "")).startswith(data_ref)
        ]

        concluidas = [p for p in producoes_hoje if p.get("estado") in ("Concluída", "Entregue")]
        canceladas = [p for p in producoes_hoje if p.get("estado") == "Cancelada"]
        em_curso_hoje = [p for p in producoes_hoje if p.get("estado") in ("Em Andamento", "A Imprimir")]
        com_nc = [p for p in producoes_hoje if p.get("nc_codigo")]

        total_horas = sum(
            ProducaoService.converter_para_horas(ProducaoService.normalizar_tempo(p))
            for p in producoes_hoje
        )

        # Produções em curso de QUALQUER dia (não fecharam ainda) —
        # diferente de "em_curso_hoje", que só conta as iniciadas hoje.
        em_curso_geral = [p for p in todas_producoes if p.get("estado") in ("Em Andamento", "A Imprimir")]

        maquinas = MaquinaService.obter_todas()
        maquinas_paradas = [
            m for m in maquinas
            if isinstance(m, dict) and m.get("estado") != "Operacional"
        ]

        return {
            "data_referencia": data_ref,
            "concluidas": concluidas,
            "canceladas": canceladas,
            "em_curso_hoje": em_curso_hoje,
            "com_nc": com_nc,
            "total_horas": total_horas,
            "em_curso_geral": em_curso_geral,
            "maquinas_paradas": maquinas_paradas,
            "id_para_nome": id_para_nome,
        }

    # ── Controlo de "já visto hoje" (por máquina/operador) ────────────────

    @staticmethod
    def _caminho_marcador(data_referencia: str) -> str:
        os.makedirs(ResumoDiarioService._MARCADOR_DIR, exist_ok=True)
        return os.path.join(ResumoDiarioService._MARCADOR_DIR, f"resumo_visto_{data_referencia}.flag")

    @staticmethod
    def ja_visto_hoje(data_referencia: str = None) -> bool:
        """Verifica se o resumo já foi mostrado automaticamente hoje,
        nesta máquina. Cada operador/PC tem o seu próprio marcador — não
        depende de outros utilizadores terem ou não visto o deles."""
        data_ref = data_referencia or datetime.now().strftime("%Y-%m-%d")
        return os.path.exists(ResumoDiarioService._caminho_marcador(data_ref))

    @staticmethod
    def marcar_visto(data_referencia: str = None):
        """Marca o resumo de hoje como já mostrado — a app não volta a
        abrir a janela automaticamente até ao dia seguinte."""
        data_ref = data_referencia or datetime.now().strftime("%Y-%m-%d")
        caminho = ResumoDiarioService._caminho_marcador(data_ref)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(f"visto em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
