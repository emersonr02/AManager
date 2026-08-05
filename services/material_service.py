from database.json_manager import JSONManager
from config.paths import ARQUIVO_MATERIAIS


class MaterialService:

    @staticmethod
    def _normalizar(entrada):
        """Converte uma entrada legada (string 'nome - fabricante') para o formato canónico."""
        if isinstance(entrada, dict):
            return {
                "nome": entrada.get("nome", entrada.get("material", entrada.get("nome_material", ""))),
                "fabricante": entrada.get("fabricante", ""),
                "ativo": entrada.get("ativo", True),
            }
        texto = str(entrada)
        if " - " in texto:
            nome_m, fab = texto.split(" - ", 1)
        else:
            nome_m, fab = texto, ""
        return {"nome": nome_m.strip(), "fabricante": fab.strip(), "ativo": True}

    @staticmethod
    def obter_todos(incluir_inativos: bool = False):
        materiais = [MaterialService._normalizar(m) for m in JSONManager.carregar(ARQUIVO_MATERIAIS)]
        if incluir_inativos:
            return materiais
        return [m for m in materiais if m.get("ativo", True)]

    @staticmethod
    def _existe(materiais, nome, fabricante):
        return any(m["nome"] == nome and m["fabricante"] == fabricante for m in materiais)

    @staticmethod
    def criar_material(nome: str, fabricante: str = ""):
        def _transformar(materiais):
            normalizados = [MaterialService._normalizar(m) for m in materiais]
            if MaterialService._existe(normalizados, nome, fabricante):
                raise ValueError("Este material já existe.")
            normalizados.append({"nome": nome, "fabricante": fabricante, "ativo": True})
            return normalizados

        return JSONManager.atualizar(ARQUIVO_MATERIAIS, _transformar)

    @staticmethod
    def atualizar_material(nome_atual: str, fabricante_atual: str, novo_nome: str, novo_fabricante: str):
        def _transformar(materiais):
            normalizados = [MaterialService._normalizar(m) for m in materiais]
            mudou_chave = (novo_nome, novo_fabricante) != (nome_atual, fabricante_atual)
            if mudou_chave and MaterialService._existe(normalizados, novo_nome, novo_fabricante):
                raise ValueError("Já existe um material com esse nome e fabricante.")
            for m in normalizados:
                if m["nome"] == nome_atual and m["fabricante"] == fabricante_atual:
                    m["nome"] = novo_nome
                    m["fabricante"] = novo_fabricante
                    break
            return normalizados

        return JSONManager.atualizar(ARQUIVO_MATERIAIS, _transformar)

    @staticmethod
    def definir_ativo(nome: str, fabricante: str, ativo: bool):
        def _transformar(materiais):
            normalizados = [MaterialService._normalizar(m) for m in materiais]
            for m in normalizados:
                if m["nome"] == nome and m["fabricante"] == fabricante:
                    m["ativo"] = ativo
                    break
            return normalizados

        return JSONManager.atualizar(ARQUIVO_MATERIAIS, _transformar)
