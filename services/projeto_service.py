from database.json_manager import JSONManager
from config.paths import ARQUIVO_PROJETOS


class ProjetoService:

    @staticmethod
    def _normalizar(entrada):
        """Converte uma entrada legada (string 'id - nome') para o formato canónico."""
        if isinstance(entrada, dict):
            return {
                "id": str(entrada.get("id", entrada.get("nr_projeto", entrada.get("numero", "")))),
                "nome": entrada.get("nome", entrada.get("nome_projeto", "")),
                "ativo": entrada.get("ativo", True),
            }
        texto = str(entrada)
        if " - " in texto:
            id_p, nome_p = texto.split(" - ", 1)
        else:
            id_p, nome_p = texto, ""
        return {"id": id_p.strip(), "nome": nome_p.strip(), "ativo": True}

    @staticmethod
    def obter_todos(incluir_inativos: bool = False):
        projetos = [ProjetoService._normalizar(p) for p in JSONManager.carregar(ARQUIVO_PROJETOS)]
        if incluir_inativos:
            return projetos
        return [p for p in projetos if p.get("ativo", True)]

    @staticmethod
    def criar_projeto(id_projeto: str, nome: str):
        def _transformar(projetos):
            normalizados = [ProjetoService._normalizar(p) for p in projetos]
            if any(p["id"] == id_projeto for p in normalizados):
                raise ValueError(f"Já existe um projeto com o ID '{id_projeto}'.")
            normalizados.append({"id": id_projeto, "nome": nome, "ativo": True})
            return normalizados

        return JSONManager.atualizar(ARQUIVO_PROJETOS, _transformar)

    @staticmethod
    def atualizar_projeto(id_atual: str, novo_id: str, novo_nome: str):
        def _transformar(projetos):
            normalizados = [ProjetoService._normalizar(p) for p in projetos]
            if novo_id != id_atual and any(p["id"] == novo_id for p in normalizados):
                raise ValueError(f"Já existe um projeto com o ID '{novo_id}'.")
            for p in normalizados:
                if p["id"] == id_atual:
                    p["id"] = novo_id
                    p["nome"] = novo_nome
                    break
            return normalizados

        return JSONManager.atualizar(ARQUIVO_PROJETOS, _transformar)

    @staticmethod
    def definir_ativo(id_projeto: str, ativo: bool):
        def _transformar(projetos):
            normalizados = [ProjetoService._normalizar(p) for p in projetos]
            for p in normalizados:
                if p["id"] == id_projeto:
                    p["ativo"] = ativo
                    break
            return normalizados

        return JSONManager.atualizar(ARQUIVO_PROJETOS, _transformar)
