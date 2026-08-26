"""
NCService — catálogo de não-conformidades e ações corretivas, sobre SQLite.

A relação "que códigos NC cada ação resolve" passou a ser uma tabela N:N
(acoes_codigos_aplicaveis) em vez de uma lista embutida em JSON, o que
permite fazer o filtro diretamente em SQL em vez de percorrer tudo em
Python a cada chamada.
"""
import json

from database.sqlite_manager import SQLiteManager


class NCService:

    @staticmethod
    def garantir_arquivos():
        """Mantido por compatibilidade com chamadas existentes. Com SQLite,
        garantir o esquema é responsabilidade do arranque da app (main.py),
        por isso aqui é uma no-op barata em vez de criar ficheiros."""
        SQLiteManager.garantir_esquema()

    @staticmethod
    def obter_nc_por_tecnologia(tecnologia):
        """
        Recebe 'FDM', 'SLA' ou 'SLS'.
        Retorna uma lista formatada: ['COD001 - Obstrução...', 'COD002 - Falha...']
        """
        with SQLiteManager.conectar() as con:
            rows = con.execute(
                "SELECT cod, descricao FROM nc_falhas WHERE tecnologia = ? ORDER BY cod",
                (tecnologia,),
            ).fetchall()
            return [f"{r['cod']} - {r['descricao']}" for r in rows]

    @staticmethod
    def obter_descricao(cod_alvo):
        """Recebe um código (ex: 'COD001') e devolve a descrição registada
        para esse código, ou string vazia se não existir."""
        with SQLiteManager.conectar() as con:
            row = con.execute("SELECT descricao FROM nc_falhas WHERE cod = ?", (cod_alvo,)).fetchone()
            return row["descricao"] if row else ""

    @staticmethod
    def _montar_acao(row) -> dict:
        d = dict(row)
        try:
            d["etapas"] = json.loads(d.get("etapas") or "[]")
        except (TypeError, json.JSONDecodeError):
            d["etapas"] = []
        return d

    @staticmethod
    def obter_acoes_por_cod(cod_alvo):
        """
        Recebe um código (ex: 'COD001') e devolve uma lista de dicionários
        com todas as ações e passos aplicáveis a esse erro.
        """
        if not cod_alvo:
            return []
        with SQLiteManager.conectar() as con:
            rows = con.execute(
                """SELECT a.* FROM acoes_corretivas a
                   JOIN acoes_codigos_aplicaveis ac ON ac.act = a.act
                   WHERE ac.nc_cod = ?
                   ORDER BY a.act""",
                (cod_alvo,),
            ).fetchall()
            return [NCService._montar_acao(r) for r in rows]

    @staticmethod
    def obter_nome_acao(act_cod: str) -> str:
        """Resolve um código de ação (ex: 'ACT001') para o texto legível
        ('Limpeza do nozzle'). Devolve o próprio código se não encontrar,
        para nunca perder rasto de dados antigos referenciando ações
        entretanto removidas do catálogo."""
        with SQLiteManager.conectar() as con:
            row = con.execute("SELECT acao FROM acoes_corretivas WHERE act = ?", (act_cod,)).fetchone()
            return row["acao"] if row and row["acao"] else act_cod

    @staticmethod
    def formatar_acoes_aplicadas(lista_act_cods: list) -> str:
        """Converte uma lista de códigos de ação aplicados (ex: ['ACT001', 'ACT004'])
        numa string legível para CSV/PDF: 'Limpeza do nozzle; Troca do filamento'.
        Lista vazia ou None devolve string vazia."""
        if not lista_act_cods:
            return ""
        return "; ".join(NCService.obter_nome_acao(c) for c in lista_act_cods)

    @staticmethod
    def detectar_recorrencia(nome_maquina: str, id_para_nome: dict = None,
                             dias: int = 7, minimo: int = 2) -> dict:
        """Verifica se algum código de NC se repetiu na máquina indicada
        dentro da janela de dias mais recente, SEM que nenhuma dessas
        ocorrências tenha tido ação corretiva confirmada (loop CAPA aberto).

        Devolve {nc_codigo: contagem} apenas para os códigos que:
        - atingiram ou ultrapassaram 'minimo' ocorrências no período, E
        - nenhuma dessas ocorrências teve 'acoes_aplicadas' preenchido.

        Um problema que já foi corrigido (mesmo que tenha ocorrido antes)
        não gera alerta — o alerta é para o que continua por resolver.
        """
        from datetime import datetime, timedelta

        if not nome_maquina:
            return {}

        limite = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")

        with SQLiteManager.conectar() as con:
            # Conta ocorrências por código e, em simultâneo, quantas dessas
            # já têm pelo menos uma ação corretiva confirmada. Substitui o
            # varrimento completo em Python que a versão JSON precisava.
            rows = con.execute(
                """SELECT p.nc_codigo AS cod,
                          COUNT(*) AS total,
                          SUM(CASE WHEN EXISTS (
                              SELECT 1 FROM producao_acoes_aplicadas paa
                              WHERE paa.producao_id = p.id
                          ) THEN 1 ELSE 0 END) AS com_acao
                     FROM producoes p
                    WHERE p.maquina_nome = ?
                      AND p.nc_codigo IS NOT NULL AND p.nc_codigo != ''
                      AND substr(p.data_inicio, 1, 10) >= ?
                    GROUP BY p.nc_codigo""",
                (nome_maquina, limite),
            ).fetchall()

        return {
            r["cod"]: r["total"]
            for r in rows
            if r["total"] >= minimo and not r["com_acao"]
        }

    @staticmethod
    def formatar_alerta_recorrencia(recorrencias: dict) -> str:
        """Formata o dict de detectar_recorrencia numa mensagem legível
        para mostrar ao operador."""
        if not recorrencias:
            return ""
        linhas = []
        for cod, cnt in sorted(recorrencias.items(), key=lambda x: -x[1]):
            desc = NCService.obter_descricao(cod)
            linhas.append(f"{cod} ({desc}): {cnt}x sem correção confirmada")
        return "\n".join(linhas)
