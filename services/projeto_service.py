"""
ProjetoService — catálogo de projetos, sobre SQLite.

A lógica _normalizar (que aceitava tanto dicts como strings legadas
"id - nome") deixa de ser necessária em runtime: os dados na BD estão
sempre no formato canónico, porque a conversão foi feita uma única vez
pelo script de migração. Mantém-se o método por compatibilidade com
quem ainda lhe chame diretamente.
"""
from database.sqlite_manager import SQLiteManager


class ProjetoService:

    @staticmethod
    def _normalizar(entrada):
        """Converte uma entrada legada (string 'id - nome') para o formato canónico.
        Com os dados já em SQLite isto raramente é preciso, mas mantém-se para
        normalizar inputs vindos de fontes externas (ex: importação de email)."""
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
        with SQLiteManager.conectar() as con:
            if incluir_inativos:
                rows = con.execute("SELECT * FROM projetos ORDER BY id").fetchall()
            else:
                rows = con.execute("SELECT * FROM projetos WHERE ativo = 1 ORDER BY id").fetchall()
            return [{"id": r["id"], "nome": r["nome"], "ativo": bool(r["ativo"])} for r in rows]

    @staticmethod
    def criar_projeto(id_projeto: str, nome: str):
        with SQLiteManager.conectar() as con:
            existe = con.execute("SELECT 1 FROM projetos WHERE id = ?", (id_projeto,)).fetchone()
            if existe:
                raise ValueError(f"Já existe um projeto com o ID '{id_projeto}'.")
            con.execute(
                "INSERT INTO projetos (id, nome, ativo) VALUES (?, ?, 1)",
                (id_projeto, nome),
            )

    @staticmethod
    def atualizar_projeto(id_atual: str, novo_id: str, novo_nome: str):
        with SQLiteManager.conectar() as con:
            if novo_id != id_atual:
                existe = con.execute("SELECT 1 FROM projetos WHERE id = ?", (novo_id,)).fetchone()
                if existe:
                    raise ValueError(f"Já existe um projeto com o ID '{novo_id}'.")
            con.execute(
                "UPDATE projetos SET id = ?, nome = ? WHERE id = ?",
                (novo_id, novo_nome, id_atual),
            )

    @staticmethod
    def definir_ativo(id_projeto: str, ativo: bool):
        with SQLiteManager.conectar() as con:
            con.execute(
                "UPDATE projetos SET ativo = ? WHERE id = ?",
                (1 if ativo else 0, id_projeto),
            )
