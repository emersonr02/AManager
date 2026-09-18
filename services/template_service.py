"""
TemplateService — gestão de templates de produção reutilizáveis.
Um template guarda os parâmetros comuns de um job recorrente (tecnologia,
máquina, tempo estimado, material, checklist) para pré-preencher a tab
de Nova Produção com um clique.
"""
import os
from datetime import datetime
from database.json_manager import JSONManager
from config.paths import ARQUIVO_TEMPLATES


class TemplateService:

    @staticmethod
    def garantir_arquivo():
        if not os.path.exists(ARQUIVO_TEMPLATES):
            JSONManager.salvar([], ARQUIVO_TEMPLATES)

    @staticmethod
    def obter_todos() -> list:
        TemplateService.garantir_arquivo()
        return JSONManager.carregar(ARQUIVO_TEMPLATES)

    @staticmethod
    def obter_por_tecnologia(tecnologia: str) -> list:
        return [t for t in TemplateService.obter_todos() if t.get("tecnologia") == tecnologia]

    @staticmethod
    def obter_por_id(id_template: int):
        for t in TemplateService.obter_todos():
            if t.get("id") == id_template:
                return t
        return None

    @staticmethod
    def criar_template(nome: str, tecnologia: str, id_maquina: str,
                       tempo_estimado: str, material: str = "",
                       altura_cuba: str = "", percentagem_po: str = "",
                       nr_projeto: str = "", nome_projeto: str = "") -> dict:
        """Cria e persiste um novo template. Retorna o dicionário criado."""
        templates = TemplateService.obter_todos()
        novo_id = max([int(t.get("id", 0)) for t in templates], default=0) + 1

        novo = {
            "id": novo_id,
            "nome": nome,
            "tecnologia": tecnologia,
            "id_maquina": id_maquina,
            "tempo_estimado": tempo_estimado,
            "material": material,
            "altura_cuba": altura_cuba,
            "percentagem_po": percentagem_po,
            "nr_projeto": nr_projeto,
            "nome_projeto": nome_projeto,
            "criado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "uso_count": 0,
        }

        def _transformar(lst):
            lst.append(novo)
            return lst
        JSONManager.atualizar(ARQUIVO_TEMPLATES, _transformar)
        return novo

    @staticmethod
    def registar_uso(id_template: int):
        """Incrementa o contador de utilização — permite ordenar por popularidade."""
        def _transformar(lst):
            for t in lst:
                if t.get("id") == id_template:
                    t["uso_count"] = t.get("uso_count", 0) + 1
                    t["ultimo_uso"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return lst
        JSONManager.atualizar(ARQUIVO_TEMPLATES, _transformar)

    @staticmethod
    def remover_template(id_template: int):
        JSONManager.atualizar(
            ARQUIVO_TEMPLATES,
            lambda lst: [t for t in lst if t.get("id") != id_template]
        )

    @staticmethod
    def criar_a_partir_de_producao(producao: dict, nome: str) -> dict:
        """Cria um template com base numa produção já existente — atalho
        para 'guardar este job como template' a partir do histórico."""
        return TemplateService.criar_template(
            nome=nome,
            tecnologia=producao.get("tecnologia", ""),
            id_maquina=producao.get("id_maquina", ""),
            tempo_estimado=producao.get("tempo_estimado") or producao.get("hora_maquina", ""),
            material=producao.get("material", ""),
            altura_cuba=str(producao.get("altura_cuba", "")),
            percentagem_po=str(producao.get("percentagem_po_novo", "")),
            nr_projeto=producao.get("nr_projeto", ""),
            nome_projeto=producao.get("nome_projeto", ""),
        )
