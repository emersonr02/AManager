"""
AuditService — trilha de auditoria append-only.

Regista quem mudou o quê, quando, e qual era o valor anterior, para
qualquer edição feita DEPOIS da criação de um registo (produção, pedido,
máquina, etc). A criação inicial já tem o seu próprio rasto (operador,
data_inicio); este serviço cobre as edições posteriores, que antes não
deixavam nenhum rasto.

O log é append-only: nunca se apaga nem edita uma entrada já escrita.
"""
import os
from datetime import datetime

from database.json_manager import JSONManager
from config.paths import ARQUIVO_AUDIT_LOG


class AuditService:

    @staticmethod
    def garantir_arquivo():
        if not os.path.exists(ARQUIVO_AUDIT_LOG):
            JSONManager.salvar([], ARQUIVO_AUDIT_LOG)

    @staticmethod
    def registrar(entidade: str, id_entidade, campo: str,
                  valor_anterior, valor_novo, utilizador: str = None) -> dict:
        """Adiciona uma entrada ao log de auditoria.

        entidade: tipo de registo alterado ('producao', 'pedido', 'maquina', ...)
        id_entidade: identificador do registo (o seu campo 'id')
        campo: nome do campo alterado (ex: 'estado', 'quantidade_real')
        valor_anterior / valor_novo: os valores antes e depois da mudança
        utilizador: quem fez a alteração; usa o utilizador de sessão se omitido

        Não regista nada se o valor não mudou de facto (evita ruído no log).
        """
        if valor_anterior == valor_novo:
            return None

        AuditService.garantir_arquivo()
        entrada = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "utilizador": utilizador or os.environ.get("USERNAME", "Desconhecido"),
            "entidade": entidade,
            "id_entidade": id_entidade,
            "campo": campo,
            "valor_anterior": valor_anterior,
            "valor_novo": valor_novo,
        }

        def _transformar(log):
            log.append(entrada)
            return log
        JSONManager.atualizar(ARQUIVO_AUDIT_LOG, _transformar)
        return entrada

    @staticmethod
    def registrar_diferencas(entidade: str, id_entidade, dados_antigos: dict,
                             dados_novos: dict, campos_relevantes: list,
                             utilizador: str = None) -> list:
        """Compara dois dicionários campo a campo (apenas os indicados em
        'campos_relevantes') e regista uma entrada de auditoria para cada
        diferença encontrada. Devolve a lista de entradas criadas.

        Usar isto em vez de chamar registrar() campo a campo manualmente
        sempre que um formulário de edição grava várias alterações de uma
        vez (ex: fecho de ordem, edição de pedido)."""
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
        entidade e/ou id específico. Sem filtros, devolve tudo (histórico
        completo) ordenado do mais recente para o mais antigo."""
        AuditService.garantir_arquivo()
        log = JSONManager.carregar(ARQUIVO_AUDIT_LOG)

        if entidade:
            log = [e for e in log if e.get("entidade") == entidade]
        if id_entidade is not None:
            log = [e for e in log if e.get("id_entidade") == id_entidade]

        return sorted(log, key=lambda e: e.get("timestamp", ""), reverse=True)

    @staticmethod
    def formatar_entrada(entrada: dict) -> str:
        """Formata uma entrada do log numa linha legível para UI/relatórios."""
        return (
            f"[{entrada.get('timestamp', '')}] {entrada.get('utilizador', '')} alterou "
            f"'{entrada.get('campo', '')}' de {entrada.get('valor_anterior')!r} "
            f"para {entrada.get('valor_novo')!r}"
        )
