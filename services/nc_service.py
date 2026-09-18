from database.json_manager import JSONManager
from config.paths import ARQUIVO_NC_FALHAS, ARQUIVO_ACOES
import os

class NCService:
    
    @staticmethod
    def garantir_arquivos():
        """Garante que os ficheiros existem antes da leitura, para evitar erros no primeiro arranque"""
        if not os.path.exists(ARQUIVO_NC_FALHAS):
            JSONManager.salvar([], ARQUIVO_NC_FALHAS)
        if not os.path.exists(ARQUIVO_ACOES):
            JSONManager.salvar([], ARQUIVO_ACOES)

    @staticmethod
    def obter_nc_por_tecnologia(tecnologia):
        """
        Recebe 'FDM', 'SLA' ou 'SLS'.
        Retorna uma lista formatada: ['COD001 - Obstrução...', 'COD002 - Falha...']
        """
        NCService.garantir_arquivos()
        ncs = JSONManager.carregar(ARQUIVO_NC_FALHAS)
        
        lista_formatada = []
        for nc in ncs:
            if nc.get("tecnologia") == tecnologia:
                lista_formatada.append(f"{nc.get('cod')} - {nc.get('descricao')}")
                
        return lista_formatada

    @staticmethod
    def obter_descricao(cod_alvo):
        """Recebe um código (ex: 'COD001') e devolve a descrição registada
        para esse código, ou string vazia se não existir."""
        NCService.garantir_arquivos()
        ncs = JSONManager.carregar(ARQUIVO_NC_FALHAS)
        for nc in ncs:
            if nc.get("cod") == cod_alvo:
                return nc.get("descricao", "")
        return ""

    @staticmethod
    def obter_acoes_por_cod(cod_alvo):
        """
        Recebe um código (ex: 'COD001') e devolve uma lista de dicionários 
        com todas as ações e passos aplicáveis a esse erro.
        """
        NCService.garantir_arquivos()
        acoes = JSONManager.carregar(ARQUIVO_ACOES)
        
        acoes_sugeridas = []
        for acao in acoes:
            # Verifica se o erro detetado está na lista de códigos que esta ação resolve
            if cod_alvo in acao.get("codigos_aplicaveis", []):
                acoes_sugeridas.append(acao)
                
        return acoes_sugeridas

    @staticmethod
    def obter_nome_acao(act_cod: str) -> str:
        """Resolve um código de ação (ex: 'ACT001') para o texto legível
        ('Limpeza do nozzle'). Devolve o próprio código se não encontrar,
        para nunca perder rasto de dados antigos referenciando ações
        entretanto removidas do catálogo."""
        NCService.garantir_arquivos()
        acoes = JSONManager.carregar(ARQUIVO_ACOES)
        for a in acoes:
            if a.get("act") == act_cod:
                return a.get("acao", act_cod)
        return act_cod

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
        from services.producao_service import ProducaoService
        from datetime import datetime, timedelta

        if id_para_nome is None:
            id_para_nome = {}
        if not nome_maquina:
            return {}

        limite = datetime.now() - timedelta(days=dias)
        contagem: dict = {}
        tem_acao: dict = {}

        for p in ProducaoService.obter_todos():
            nc_cod = p.get("nc_codigo", "")
            if not nc_cod:
                continue
            if ProducaoService.normalizar_maquina(p, id_para_nome) != nome_maquina:
                continue

            raw = str(p.get("data_inicio", "")).strip()
            dt = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    continue
            if dt is None or dt < limite:
                continue

            contagem[nc_cod] = contagem.get(nc_cod, 0) + 1
            if p.get("acoes_aplicadas"):
                tem_acao[nc_cod] = True

        return {
            cod: cnt for cod, cnt in contagem.items()
            if cnt >= minimo and not tem_acao.get(cod, False)
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