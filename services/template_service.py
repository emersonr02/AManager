"""
TemplateService — templates de produção reutilizáveis, sobre SQLite.

Um template guarda os parâmetros comuns de um job recorrente (tecnologia,
máquina, tempo estimado, material, checklist) para pré-preencher a tab
de Nova Produção com um clique.
"""
from datetime import datetime

from database.sqlite_manager import SQLiteManager


class TemplateService:

    @staticmethod
    def garantir_arquivo():
        """Mantido por compatibilidade. Com SQLite, o esquema é garantido
        no arranque da app (main.py)."""
        SQLiteManager.garantir_esquema()

    @staticmethod
    def obter_todos() -> list:
        with SQLiteManager.conectar() as con:
            rows = con.execute("SELECT * FROM templates_producao ORDER BY id").fetchall()
            return SQLiteManager.dicts_de_linhas(rows)

    @staticmethod
    def obter_por_tecnologia(tecnologia: str) -> list:
        with SQLiteManager.conectar() as con:
            rows = con.execute(
                "SELECT * FROM templates_producao WHERE tecnologia = ? ORDER BY uso_count DESC, id",
                (tecnologia,),
            ).fetchall()
            return SQLiteManager.dicts_de_linhas(rows)

    @staticmethod
    def obter_por_id(id_template: int):
        with SQLiteManager.conectar() as con:
            row = con.execute(
                "SELECT * FROM templates_producao WHERE id = ?", (id_template,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def criar_template(nome: str, tecnologia: str, id_maquina: str,
                       tempo_estimado: str, material: str = "",
                       altura_cuba: str = "", percentagem_po: str = "",
                       nr_projeto: str = "", nome_projeto: str = "") -> dict:
        """Cria e persiste um novo template. Retorna o dicionário criado."""
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with SQLiteManager.conectar() as con:
            cur = con.execute(
                """INSERT INTO templates_producao (
                    nome, tecnologia, id_maquina, tempo_estimado, material,
                    altura_cuba, percentagem_po, nr_projeto, nome_projeto,
                    criado_em, uso_count, ultimo_uso
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '')""",
                (nome, tecnologia, id_maquina, tempo_estimado, material,
                 altura_cuba, percentagem_po, nr_projeto, nome_projeto, agora),
            )
            novo_id = cur.lastrowid
            row = con.execute(
                "SELECT * FROM templates_producao WHERE id = ?", (novo_id,)
            ).fetchone()
            return dict(row)

    @staticmethod
    def registar_uso(id_template: int):
        """Incrementa o contador de utilização — permite ordenar por popularidade."""
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with SQLiteManager.conectar() as con:
            con.execute(
                "UPDATE templates_producao SET uso_count = uso_count + 1, ultimo_uso = ? WHERE id = ?",
                (agora, id_template),
            )

    @staticmethod
    def remover_template(id_template: int):
        with SQLiteManager.conectar() as con:
            con.execute("DELETE FROM templates_producao WHERE id = ?", (id_template,))

    @staticmethod
    def criar_a_partir_de_producao(producao: dict, nome: str) -> dict:
        """Cria um template com base numa produção já existente — atalho
        para 'guardar este job como template' a partir do histórico."""
        return TemplateService.criar_template(
            nome=nome,
            tecnologia=producao.get("tecnologia", ""),
            id_maquina=producao.get("id_maquina") or "",
            tempo_estimado=producao.get("tempo_estimado") or producao.get("hora_maquina", ""),
            material=producao.get("material", ""),
            altura_cuba=str(producao.get("altura_cuba", "")),
            percentagem_po=str(producao.get("percentagem_po_novo", "")),
            nr_projeto=producao.get("nr_projeto", ""),
            nome_projeto=producao.get("nome_projeto", ""),
        )
