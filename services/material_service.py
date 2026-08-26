"""
MaterialService — catálogo de materiais, sobre SQLite.

A chave de negócio é o par (nome, fabricante) — garantida por uma
constraint UNIQUE no esquema, em vez de ser verificada manualmente em
Python a cada operação como acontecia na versão JSON.
"""
from database.sqlite_manager import SQLiteManager


class MaterialService:

    @staticmethod
    def _normalizar(entrada):
        """Converte uma entrada legada (string 'nome - fabricante') para o
        formato canónico. Com os dados já em SQLite raramente é preciso,
        mas mantém-se para normalizar inputs de fontes externas."""
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
        with SQLiteManager.conectar() as con:
            if incluir_inativos:
                rows = con.execute("SELECT * FROM materiais ORDER BY nome, fabricante").fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM materiais WHERE ativo = 1 ORDER BY nome, fabricante"
                ).fetchall()
            return [
                {"nome": r["nome"], "fabricante": r["fabricante"], "ativo": bool(r["ativo"])}
                for r in rows
            ]

    @staticmethod
    def _existe(con, nome, fabricante) -> bool:
        row = con.execute(
            "SELECT 1 FROM materiais WHERE nome = ? AND fabricante = ?", (nome, fabricante)
        ).fetchone()
        return row is not None

    @staticmethod
    def criar_material(nome: str, fabricante: str = ""):
        with SQLiteManager.conectar() as con:
            if MaterialService._existe(con, nome, fabricante):
                raise ValueError("Este material já existe.")
            con.execute(
                "INSERT INTO materiais (nome, fabricante, ativo) VALUES (?, ?, 1)",
                (nome, fabricante),
            )

    @staticmethod
    def atualizar_material(nome_atual: str, fabricante_atual: str, novo_nome: str, novo_fabricante: str):
        with SQLiteManager.conectar() as con:
            mudou_chave = (novo_nome, novo_fabricante) != (nome_atual, fabricante_atual)
            if mudou_chave and MaterialService._existe(con, novo_nome, novo_fabricante):
                raise ValueError("Já existe um material com esse nome e fabricante.")
            con.execute(
                "UPDATE materiais SET nome = ?, fabricante = ? WHERE nome = ? AND fabricante = ?",
                (novo_nome, novo_fabricante, nome_atual, fabricante_atual),
            )

    @staticmethod
    def definir_ativo(nome: str, fabricante: str, ativo: bool):
        with SQLiteManager.conectar() as con:
            con.execute(
                "UPDATE materiais SET ativo = ? WHERE nome = ? AND fabricante = ?",
                (1 if ativo else 0, nome, fabricante),
            )
