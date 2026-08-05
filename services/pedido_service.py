from datetime import datetime
from database.json_manager import JSONManager
from config.paths import ARQUIVO_PEDIDOS

class PedidoService:
    
    @staticmethod
    def obter_todos():
        """Retorna todos os pedidos ordenados do mais recente para o mais antigo."""
        pedidos = JSONManager.carregar(ARQUIVO_PEDIDOS)
        pedidos.sort(key=lambda x: int(x.get("id", 0)), reverse=True)
        return pedidos

    @staticmethod
    def criar_pedido(requerente: str, projeto: str, tecnologia: str, responsavel: str, observacao: str):
        """Aplica a regra de negócio para gerar um novo ID e salvar o pedido."""
        hoje = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Regra de negócio: limpa o nome do projeto se vier no formato "ID - Nome"
        projeto_limpo = projeto.split(" - ")[0] if " - " in projeto else projeto

        novo_pedido = {}

        def _transformar(pedidos):
            novo_id = max([p.get("id", 0) for p in pedidos]) + 1 if pedidos else 1
            novo_pedido.update({
                "id": novo_id,
                "requerente": requerente,
                "projeto": projeto_limpo,
                "tecnologia": tecnologia,
                "responsavel": responsavel,
                "status": "Em Andamento",
                "observacao": observacao,
                "data_pedido": hoje,
                "data_atualizacao": hoje
            })
            pedidos.append(novo_pedido)
            return pedidos

        # Lê, calcula o novo ID e grava sob um único lock, para dois pedidos
        # criados ao mesmo tempo (rede partilhada) não colidirem no mesmo ID.
        JSONManager.atualizar(ARQUIVO_PEDIDOS, _transformar)
        return novo_pedido

    @staticmethod
    def atualizar_pedido(pedido_atualizado: dict):
        """Atualiza um pedido existente e renova a data de atualização."""
        pedido_atualizado["data_atualizacao"] = datetime.now().strftime("%Y-%m-%d %H:%M")

        def _transformar(pedidos):
            for idx, p in enumerate(pedidos):
                if p.get("id") == pedido_atualizado.get("id"):
                    pedidos[idx] = pedido_atualizado
                    break
            return pedidos

        JSONManager.atualizar(ARQUIVO_PEDIDOS, _transformar)
        return pedido_atualizado