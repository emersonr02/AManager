"""
BackupService — snapshots automáticos da base de dados SQLite.

Usa a API nativa de backup do SQLite (con.backup()) em vez de copiar o
ficheiro com shutil: isso garante um snapshot consistente mesmo que
outra pessoa esteja a escrever na BD no preciso momento do backup —
uma cópia crua do ficheiro poderia apanhar um estado intermédio, ainda
mais provável em WAL mode, onde parte dos dados vive no ficheiro -wal.
"""
import os
import glob
import shutil
import sqlite3
from datetime import datetime

from config.paths import DATA_DIR, BACKUP_DIR
from database.sqlite_manager import ARQUIVO_DB


class BackupService:

    @staticmethod
    def _garantir_pasta_backups():
        os.makedirs(BACKUP_DIR, exist_ok=True)

    @staticmethod
    def criar_snapshot(motivo: str = "manual") -> str:
        """Cria um novo snapshot consistente da base de dados.
        Devolve o caminho da pasta de backup criada."""
        BackupService._garantir_pasta_backups()

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        caminho_snapshot = os.path.join(BACKUP_DIR, f"{timestamp}_{motivo}")
        os.makedirs(caminho_snapshot, exist_ok=True)

        destino_db = os.path.join(caminho_snapshot, "amanager.db")

        if os.path.exists(ARQUIVO_DB):
            # API nativa de backup: transacionalmente segura, mesmo com
            # escritas concorrentes a decorrer noutro processo.
            origem = sqlite3.connect(ARQUIVO_DB)
            try:
                destino = sqlite3.connect(destino_db)
                try:
                    origem.backup(destino)
                finally:
                    destino.close()
            finally:
                origem.close()

        return caminho_snapshot

    @staticmethod
    def ja_existe_backup_hoje() -> bool:
        """Verifica se já foi feito algum snapshot hoje (de qualquer
        motivo), para evitar duplicar o backup diário a cada arranque."""
        BackupService._garantir_pasta_backups()
        hoje = datetime.now().strftime("%Y-%m-%d")
        return any(
            nome.startswith(hoje)
            for nome in os.listdir(BACKUP_DIR)
            if os.path.isdir(os.path.join(BACKUP_DIR, nome))
        )

    @staticmethod
    def snapshot_automatico_diario():
        """Cria o backup do dia se ainda não existir nenhum. Idempotente —
        seguro chamar em todos os arranques da aplicação sem duplicar.
        Devolve o caminho criado, ou None se já havia backup de hoje."""
        if BackupService.ja_existe_backup_hoje():
            return None
        return BackupService.criar_snapshot(motivo="diario")

    @staticmethod
    def listar_backups() -> list:
        """Devolve a lista de snapshots existentes, mais recente primeiro."""
        BackupService._garantir_pasta_backups()
        resultado = []
        for nome in sorted(os.listdir(BACKUP_DIR), reverse=True):
            caminho = os.path.join(BACKUP_DIR, nome)
            if not os.path.isdir(caminho):
                continue
            caminho_db = os.path.join(caminho, "amanager.db")
            tamanho = os.path.getsize(caminho_db) if os.path.exists(caminho_db) else 0
            resultado.append({
                "nome": nome,
                "caminho": caminho,
                "tem_db": os.path.exists(caminho_db),
                "tamanho_bytes": tamanho,
            })
        return resultado

    @staticmethod
    def limpar_backups_antigos(manter: int = 30) -> int:
        """Remove os snapshots mais antigos além dos últimos 'manter',
        para não deixar a pasta de backups crescer indefinidamente.
        Devolve o número de backups removidos."""
        backups = BackupService.listar_backups()  # já vem do mais recente para o mais antigo
        excedentes = backups[manter:]
        for b in excedentes:
            shutil.rmtree(b["caminho"], ignore_errors=True)
        return len(excedentes)

    @staticmethod
    def restaurar_backup(nome_backup: str) -> str:
        """Restaura a base de dados a partir de um snapshot, substituindo a
        BD ativa. Operação manual/administrativa — nunca chamada
        automaticamente. Devolve o caminho da BD restaurada.

        IMPORTANTE: a app deve estar fechada durante o restauro."""
        caminho_snapshot = os.path.join(BACKUP_DIR, nome_backup)
        if not os.path.isdir(caminho_snapshot):
            raise FileNotFoundError(f"Backup '{nome_backup}' não encontrado.")

        origem_db = os.path.join(caminho_snapshot, "amanager.db")
        if not os.path.exists(origem_db):
            raise FileNotFoundError(f"Backup '{nome_backup}' não contém amanager.db.")

        os.makedirs(DATA_DIR, exist_ok=True)

        # Remove ficheiros auxiliares do WAL da BD atual: se ficassem para
        # trás, o SQLite tentaria reaplicá-los sobre a BD restaurada e
        # corromperia o estado que acabámos de repor.
        for sufixo in ("-wal", "-shm"):
            aux = ARQUIVO_DB + sufixo
            if os.path.exists(aux):
                os.remove(aux)

        shutil.copy2(origem_db, ARQUIVO_DB)
        return ARQUIVO_DB
