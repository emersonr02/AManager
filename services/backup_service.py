"""
BackupService — snapshots automáticos dos ficheiros JSON que servem de
base de dados. Protege contra corrupção de ficheiro, edição acidental, ou
falhas da pasta de rede partilhada — sem precisar de SQL server.

Cada snapshot é uma pasta com timestamp dentro de data/backups/, contendo
uma cópia de todos os *.json da pasta data/ nesse momento.
"""
import os
import shutil
import glob
from datetime import datetime

from config.paths import DATA_DIR, BACKUP_DIR


class BackupService:

    @staticmethod
    def _garantir_pasta_backups():
        os.makedirs(BACKUP_DIR, exist_ok=True)

    @staticmethod
    def _ficheiros_para_backup() -> list:
        """Lista todos os *.json diretamente em DATA_DIR (não desce a
        subpastas — em particular, nunca entra em BACKUP_DIR)."""
        return [
            f for f in glob.glob(os.path.join(DATA_DIR, "*.json"))
            if os.path.isfile(f)
        ]

    @staticmethod
    def criar_snapshot(motivo: str = "manual") -> str:
        """Cria um novo snapshot com todos os ficheiros JSON atuais.
        Devolve o caminho da pasta de backup criada."""
        BackupService._garantir_pasta_backups()

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        nome_pasta = f"{timestamp}_{motivo}"
        caminho_snapshot = os.path.join(BACKUP_DIR, nome_pasta)
        os.makedirs(caminho_snapshot, exist_ok=True)

        for ficheiro in BackupService._ficheiros_para_backup():
            destino = os.path.join(caminho_snapshot, os.path.basename(ficheiro))
            shutil.copy2(ficheiro, destino)

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
    def snapshot_automatico_diario() -> str | None:
        """Cria o backup do dia se ainda não existir nenhum. Idempotente —
        seguro chamar em todos os arranques da aplicação sem duplicar.
        Devolve o caminho criado, ou None se já havia backup de hoje."""
        if BackupService.ja_existe_backup_hoje():
            return None
        return BackupService.criar_snapshot(motivo="diario")

    @staticmethod
    def listar_backups() -> list:
        """Devolve a lista de snapshots existentes, mais recente primeiro,
        com nome, caminho e nº de ficheiros guardados em cada um."""
        BackupService._garantir_pasta_backups()
        resultado = []
        for nome in sorted(os.listdir(BACKUP_DIR), reverse=True):
            caminho = os.path.join(BACKUP_DIR, nome)
            if not os.path.isdir(caminho):
                continue
            n_ficheiros = len(glob.glob(os.path.join(caminho, "*.json")))
            resultado.append({"nome": nome, "caminho": caminho, "n_ficheiros": n_ficheiros})
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
    def restaurar_backup(nome_backup: str) -> list:
        """Restaura os ficheiros de um snapshot para a pasta de dados
        ativa, substituindo o conteúdo atual. Operação manual/administrativa
        — não é chamada automaticamente em nenhum fluxo normal da app.
        Devolve a lista de ficheiros restaurados."""
        caminho_snapshot = os.path.join(BACKUP_DIR, nome_backup)
        if not os.path.isdir(caminho_snapshot):
            raise FileNotFoundError(f"Backup '{nome_backup}' não encontrado.")

        restaurados = []
        for ficheiro in glob.glob(os.path.join(caminho_snapshot, "*.json")):
            destino = os.path.join(DATA_DIR, os.path.basename(ficheiro))
            shutil.copy2(ficheiro, destino)
            restaurados.append(os.path.basename(ficheiro))

        return restaurados
