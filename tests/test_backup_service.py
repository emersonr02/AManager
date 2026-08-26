"""
Testes do BackupService — snapshots da base de dados SQLite.

Usa a API nativa con.backup() em vez de cópia crua do ficheiro, o que
garante snapshots consistentes mesmo com escritas concorrentes.
"""
import os
import time
import sqlite3
import pytest


@pytest.fixture
def ambiente_backup(tmp_path, monkeypatch):
    """Isola DATA_DIR, BACKUP_DIR e a BD num diretório temporário, com
    algumas linhas já inseridas para os snapshots terem conteúdo real."""
    from services import backup_service
    from database import sqlite_manager

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    backup_dir = data_dir / "backups"
    caminho_db = data_dir / "amanager.db"

    monkeypatch.setattr(sqlite_manager, "ARQUIVO_DB", str(caminho_db))
    monkeypatch.setattr(backup_service, "ARQUIVO_DB", str(caminho_db))
    monkeypatch.setattr(backup_service, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(backup_service, "BACKUP_DIR", str(backup_dir))

    sqlite_manager.SQLiteManager.garantir_esquema()
    with sqlite_manager.SQLiteManager.conectar() as con:
        con.execute("INSERT INTO maquinas (id, nome, tech) VALUES ('X1-1', 'Bambu Lab X1C #1', 'FDM')")
        con.execute("INSERT INTO producoes (data_inicio, tecnologia, maquina_nome) "
                    "VALUES ('2026-08-01', 'FDM', 'Bambu Lab X1C #1')")

    return {"data_dir": str(data_dir), "backup_dir": str(backup_dir), "db": str(caminho_db)}


def _contar(caminho_db, tabela):
    con = sqlite3.connect(caminho_db)
    try:
        return con.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
    finally:
        con.close()


def test_criar_snapshot_gera_copia_da_bd(ambiente_backup):
    from services.backup_service import BackupService
    caminho = BackupService.criar_snapshot("manual")
    assert os.path.isdir(caminho)
    assert os.path.exists(os.path.join(caminho, "amanager.db"))


def test_criar_snapshot_preserva_conteudo(ambiente_backup):
    from services.backup_service import BackupService
    caminho = BackupService.criar_snapshot("manual")
    db_backup = os.path.join(caminho, "amanager.db")
    assert _contar(db_backup, "maquinas") == 1
    assert _contar(db_backup, "producoes") == 1


def test_criar_snapshot_sem_bd_nao_rebenta(tmp_path, monkeypatch):
    """Primeira execução, antes de qualquer BD existir: deve criar a pasta
    do snapshot sem erro, apenas sem ficheiro lá dentro."""
    from services import backup_service
    from services.backup_service import BackupService

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(backup_service, "ARQUIVO_DB", str(data_dir / "inexistente.db"))
    monkeypatch.setattr(backup_service, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(backup_service, "BACKUP_DIR", str(data_dir / "backups"))

    caminho = BackupService.criar_snapshot("manual")
    assert os.path.isdir(caminho)


def test_ja_existe_backup_hoje_inicialmente_falso(ambiente_backup):
    from services.backup_service import BackupService
    assert BackupService.ja_existe_backup_hoje() is False


def test_ja_existe_backup_hoje_apos_criar(ambiente_backup):
    from services.backup_service import BackupService
    BackupService.criar_snapshot("manual")
    assert BackupService.ja_existe_backup_hoje() is True


def test_snapshot_automatico_diario_cria_na_primeira_vez(ambiente_backup):
    from services.backup_service import BackupService
    caminho = BackupService.snapshot_automatico_diario()
    assert caminho is not None
    assert os.path.isdir(caminho)


def test_snapshot_automatico_diario_e_idempotente(ambiente_backup):
    from services.backup_service import BackupService
    primeiro = BackupService.snapshot_automatico_diario()
    segundo = BackupService.snapshot_automatico_diario()
    assert primeiro is not None
    assert segundo is None  # já havia backup de hoje — não duplica


def test_listar_backups_ordena_do_mais_recente(ambiente_backup):
    from services.backup_service import BackupService
    BackupService.criar_snapshot("primeiro")
    time.sleep(1.1)
    BackupService.criar_snapshot("segundo")
    backups = BackupService.listar_backups()
    assert len(backups) == 2
    assert "segundo" in backups[0]["nome"]
    assert "primeiro" in backups[1]["nome"]


def test_listar_backups_reporta_tamanho_e_presenca_da_bd(ambiente_backup):
    from services.backup_service import BackupService
    BackupService.criar_snapshot("manual")
    b = BackupService.listar_backups()[0]
    assert b["tem_db"] is True
    assert b["tamanho_bytes"] > 0


def test_limpar_backups_antigos_mantem_apenas_os_recentes(ambiente_backup):
    from services.backup_service import BackupService
    for i in range(4):
        BackupService.criar_snapshot(f"snap{i}")
        time.sleep(1.1)
    assert len(BackupService.listar_backups()) == 4

    removidos = BackupService.limpar_backups_antigos(manter=2)
    assert removidos == 2
    assert len(BackupService.listar_backups()) == 2


def test_limpar_backups_antigos_mantem_os_mais_recentes(ambiente_backup):
    from services.backup_service import BackupService
    for i in range(3):
        BackupService.criar_snapshot(f"snap{i}")
        time.sleep(1.1)

    BackupService.limpar_backups_antigos(manter=1)
    restantes = BackupService.listar_backups()
    assert len(restantes) == 1
    assert "snap2" in restantes[0]["nome"]  # o último criado


def test_restaurar_backup_repoe_conteudo_original(ambiente_backup):
    from services.backup_service import BackupService
    from database import sqlite_manager

    caminho = BackupService.criar_snapshot("manual")
    nome_backup = os.path.basename(caminho)

    # Altera a BD ativa depois do snapshot
    with sqlite_manager.SQLiteManager.conectar() as con:
        con.execute("DELETE FROM producoes")
    assert _contar(ambiente_backup["db"], "producoes") == 0

    BackupService.restaurar_backup(nome_backup)
    assert _contar(ambiente_backup["db"], "producoes") == 1


def test_restaurar_backup_inexistente_leva_erro(ambiente_backup):
    from services.backup_service import BackupService
    with pytest.raises(FileNotFoundError):
        BackupService.restaurar_backup("nao_existe_2020-01-01_000000_manual")


def test_restaurar_backup_sem_db_leva_erro(ambiente_backup):
    """Uma pasta de backup vazia (ex: snapshot criado antes de existir BD)
    não deve ser silenciosamente aceite como restauro válido."""
    from services.backup_service import BackupService
    vazio = os.path.join(ambiente_backup["backup_dir"], "2020-01-01_000000_vazio")
    os.makedirs(vazio, exist_ok=True)
    with pytest.raises(FileNotFoundError):
        BackupService.restaurar_backup("2020-01-01_000000_vazio")
