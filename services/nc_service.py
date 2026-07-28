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