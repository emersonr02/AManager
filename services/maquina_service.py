from database.json_manager import JSONManager
from config.paths import ARQUIVO_MAQUINAS

class MaquinaService:
    
    @staticmethod
    def obter_todas():
        """Retorna a lista completa do parque de máquinas."""
        return JSONManager.carregar(ARQUIVO_MAQUINAS)

    @staticmethod
    def obter_ativas_por_tecnologia(tecnologia: str):
        """Regra de negócio: Retorna apenas IDs de máquinas operacionais de uma tecnologia específica."""
        maquinas = JSONManager.carregar(ARQUIVO_MAQUINAS)
        return [m["id"] for m in maquinas if m.get("tech") == tecnologia and m.get("estado") == "Operacional"]

    @staticmethod
    def salvar_maquina(mid: str, nome: str, tech: str, estado: str, manutencao: str, url_img: str = ""):
        maquinas = JSONManager.carregar(ARQUIVO_MAQUINAS)
        existe = False
        
        for m in maquinas:
            if m.get("id") == mid:
                m.update({
                    "nome": nome, 
                    "tech": tech, 
                    "estado": estado, 
                    "manutencao": manutencao,
                    "url_img": url_img # Atualiza
                })
                existe = True
                break
                
        if not existe:
            maquinas.append({
                "id": mid, 
                "nome": nome, 
                "tech": tech, 
                "estado": estado, 
                "manutencao": manutencao,
                "url_img": url_img # Cria novo
            })
            
        JSONManager.salvar(maquinas, ARQUIVO_MAQUINAS)
                
        if not existe:
            maquinas.append({
                "id": mid, 
                "nome": nome, 
                "tech": tech, 
                "estado": estado, 
                "manutencao": manutencao
            })
            
        JSONManager.salvar(maquinas, ARQUIVO_MAQUINAS)

    @staticmethod
    def remover_maquina(mid: str):
        """Remove a máquina do parque pelo ID."""
        maquinas = JSONManager.carregar(ARQUIVO_MAQUINAS)
        maquinas_filtradas = [m for m in maquinas if m.get("id") != mid]
        JSONManager.salvar(maquinas_filtradas, ARQUIVO_MAQUINAS)