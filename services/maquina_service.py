"""
MaquinaService — gestão do parque de máquinas, agora sobre SQLite.

A assinatura pública de todos os métodos mantém-se idêntica à versão
JSON: quem chama obter_todas()/obter_lookup_id_nome()/etc. continua a
receber exatamente as mesmas formas de dict/list que recebia antes — só
a implementação interna mudou de ficheiro para base de dados.
"""
from database.sqlite_manager import SQLiteManager


class MaquinaService:

    @staticmethod
    def obter_todas() -> list:
        """Retorna a lista completa do parque de máquinas."""
        with SQLiteManager.conectar() as con:
            rows = con.execute("SELECT * FROM maquinas ORDER BY id").fetchall()
            return SQLiteManager.dicts_de_linhas(rows)

    @staticmethod
    def obter_lookup_id_nome() -> dict:
        """Devolve um dict {id_maquina: nome} para resolução rápida de IDs legacy."""
        return {m["id"]: m["nome"] for m in MaquinaService.obter_todas()}

    @staticmethod
    def obter_ativas_por_tecnologia(tecnologia: str) -> list:
        with SQLiteManager.conectar() as con:
            rows = con.execute(
                "SELECT id FROM maquinas WHERE tech = ? AND estado = 'Operacional' ORDER BY id",
                (tecnologia,),
            ).fetchall()
            return [r["id"] for r in rows]

    @staticmethod
    def salvar_maquina(mid: str, nome: str, tech: str, estado: str, manutencao: str, url_img: str = ""):
        """Cria a máquina se o id ainda não existir, ou atualiza-a (upsert)."""
        with SQLiteManager.conectar() as con:
            con.execute(
                """INSERT INTO maquinas (id, nome, tech, estado, manutencao, url_img)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       nome = excluded.nome, tech = excluded.tech, estado = excluded.estado,
                       manutencao = excluded.manutencao, url_img = excluded.url_img""",
                (mid, nome, tech, estado, manutencao, url_img),
            )

    @staticmethod
    def remover_maquina(mid: str):
        """Remove a máquina do parque pelo ID. Produções que já a referenciam
        (maquina_id) ficam com maquina_id=NULL automaticamente (ON DELETE
        SET NULL no esquema) — o nome histórico (maquina_nome) não se perde."""
        with SQLiteManager.conectar() as con:
            con.execute("DELETE FROM maquinas WHERE id = ?", (mid,))
