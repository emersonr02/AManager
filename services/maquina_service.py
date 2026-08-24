from database.json_manager import JSONManager
from config.paths import ARQUIVO_MAQUINAS

class MaquinaService:
    
    @staticmethod
    def obter_todas():
        """Retorna a lista completa do parque de máquinas."""
        return JSONManager.carregar(ARQUIVO_MAQUINAS)

    @staticmethod
    def obter_lookup_id_nome() -> dict:
        """Devolve um dict {id_maquina: nome} para resolução rápida de IDs legacy."""
        return {
            m.get("id"): m.get("nome")
            for m in MaquinaService.obter_todas()
            if isinstance(m, dict) and m.get("id") and m.get("nome")
        }

    @staticmethod
    def obter_ativas_por_tecnologia(tecnologia: str):
        maquinas = JSONManager.carregar(ARQUIVO_MAQUINAS)
        return [m["id"] for m in maquinas if m.get("tech") == tecnologia and m.get("estado") == "Operacional"]

    @staticmethod
    def salvar_maquina(mid: str, nome: str, tech: str, estado: str, manutencao: str, url_img: str = ""):
        def _transformar(maquinas):
            for m in maquinas:
                if m.get("id") == mid:
                    m.update({
                        "nome": nome,
                        "tech": tech,
                        "estado": estado,
                        "manutencao": manutencao,
                        "url_img": url_img  # Atualiza
                    })
                    return maquinas

            maquinas.append({
                "id": mid,
                "nome": nome,
                "tech": tech,
                "estado": estado,
                "manutencao": manutencao,
                "url_img": url_img  # Cria novo
            })
            return maquinas

        JSONManager.atualizar(ARQUIVO_MAQUINAS, _transformar)

    @staticmethod
    def remover_maquina(mid: str):
        """Remove a máquina do parque pelo ID."""
        JSONManager.atualizar(ARQUIVO_MAQUINAS, lambda maquinas: [m for m in maquinas if m.get("id") != mid])