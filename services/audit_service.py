"""
AuditService — trilha de auditoria append-only, sobre SQLite.

Regista quem mudou o quê, quando, e qual era o valor anterior, para
qualquer edição feita DEPOIS da criação de um registo (produção, pedido,
máquina, etc). A criação inicial já tem o seu próprio rasto (operador,
data_inicio); este serviço cobre as edições posteriores.

O log é append-only: nunca se apaga nem edita uma entrada já escrita.
"""
import json
import os
from datetime import datetime

from database.sqlite_manager import SQLiteManager


class AuditService:

    @staticmethod
    def garantir_arquivo():
        """Mantido por compatibilidade. Com SQLite, o esquema é garantido
        no arranque da app (main.py)."""
        SQLiteManager.garantir_esquema()

    @staticmethod
    def _serializar(valor):
        """Listas e dicts são guardados como JSON; o resto como texto.
        Preserva a distinção entre None (campo não existia) e '' (vazio)."""
        if valor is None:
            return None
        if isinstance(valor, (list, dict)):
            return json.dumps(valor, ensure_ascii=False)
        return str(valor)

    @staticmethod
    def registrar(entidade: str, id_entidade, campo: str,
                  valor_anterior, valor_novo, utilizador: str = None) -> dict:
        """Adiciona uma entrada ao log de auditoria.

        Não regista nada se o valor não mudou de facto (evita ruído no log).
        """
        if valor_anterior == valor_novo:
            return None

        entrada = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "utilizador": utilizador or os.environ.get("USERNAME", "Desconhecido"),
            "entidade": entidade,
            "id_entidade": id_entidade,
            "campo": campo,
            "valor_anterior": valor_anterior,
            "valor_novo": valor_novo,
        }

        with SQLiteManager.conectar() as con:
            con.execute(
                """INSERT INTO audit_log (timestamp, utilizador, entidade, id_entidade,
                    campo, valor_anterior, valor_novo) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (entrada["timestamp"], entrada["utilizador"], entidade, str(id_entidade), campo,
                 AuditService._serializar(valor_anterior), AuditService._serializar(valor_novo)),
            )
        return entrada

    @staticmethod
    def registrar_diferencas(entidade: str, id_entidade, dados_antigos: dict,
                             dados_novos: dict, campos_relevantes: list,
                             utilizador: str = None) -> list:
        """Compara dois dicionários campo a campo (apenas os indicados em
        'campos_relevantes') e regista uma entrada de auditoria para cada
        diferença encontrada. Devolve a lista de entradas criadas."""
        entradas = []
        for campo in campos_relevantes:
            antigo = dados_antigos.get(campo)
            novo = dados_novos.get(campo)
            entrada = AuditService.registrar(entidade, id_entidade, campo, antigo, novo, utilizador)
            if entrada:
                entradas.append(entrada)
        return entradas

    @staticmethod
    def obter_historico(entidade: str = None, id_entidade=None) -> list:
        """Devolve as entradas do log, opcionalmente filtradas por tipo de
        entidade e/ou id específico, ordenadas do mais recente para o mais
        antigo."""
        sql = "SELECT * FROM audit_log"
        condicoes, params = [], []
        if entidade:
            condicoes.append("entidade = ?")
            params.append(entidade)
        if id_entidade is not None:
            condicoes.append("id_entidade = ?")
            params.append(str(id_entidade))
        if condicoes:
            sql += " WHERE " + " AND ".join(condicoes)
        # id DESC como desempate: dois registos no mesmo segundo mantêm a
        # ordem real de inserção, o que a resolução de segundos do
        # timestamp sozinha não garantiria.
        sql += " ORDER BY timestamp DESC, id DESC"

        with SQLiteManager.conectar() as con:
            rows = con.execute(sql, params).fetchall()
            return SQLiteManager.dicts_de_linhas(rows)

    @staticmethod
    def formatar_entrada(entrada: dict) -> str:
        """Formata uma entrada do log numa linha legível para UI/relatórios."""
        return (
            f"[{entrada.get('timestamp', '')}] {entrada.get('utilizador', '')} alterou "
            f"'{entrada.get('campo', '')}' de {entrada.get('valor_anterior')!r} "
            f"para {entrada.get('valor_novo')!r}"
        )
