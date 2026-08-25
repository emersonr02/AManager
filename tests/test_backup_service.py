"""
Testes do BackupService — snapshots automáticos e rotação dos ficheiros
JSON que servem de base de dados.
"""
import os
import time
import pytest


@pytest.fixture
def ambiente_backup(tmp_path, monkeypatch):
    """Isola DATA_DIR e BACKUP_DIR num diretório temporário, com alguns
    ficheiros JSON de exemplo já criados."""
    from services import backup_service

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    backup_dir = data_dir / "backups"

    monkeypatch.setattr(backup_service, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(backup_service, "BACKUP_DIR", str(backup_dir))

    for nome, conteudo in [
        ("producao_i3D.json", '[{"id": 1}]'),
        ("pedidos.json", '[{"id": 5}]'),
        ("parque_maquinas.json", '[{"id": "X1-1"}]'),
    ]:
        (data_dir / nome).write_text(conteudo, encoding="utf-8")

    return str(data_dir), str(backup_dir)


def test_criar_snapshot_copia_todos_os_json(ambiente_backup):
    from services.backup_service import BackupService
    caminho = BackupService.criar_snapshot("manual")
    assert os.path.isdir(caminho)
    ficheiros = set(os.listdir(caminho))
    assert ficheiros == {"producao_i3D.json", "pedidos.json", "parque_maquinas.json"}


def test_criar_snapshot_preserva_conteudo(ambiente_backup):
    from services.backup_service import BackupService
    caminho = BackupService.criar_snapshot("manual")
    with open(os.path.join(caminho, "pedidos.json")) as f:
        assert f.read() == '[{"id": 5}]'


def test_criar_snapshot_nao_desce_a_subpastas(ambiente_backup):
    """Um backup anterior (pasta dentro de BACKUP_DIR) nunca deve ser
    copiado para dentro de si mesmo — só ficheiros *.json de DATA_DIR."""
    from services.backup_service import BackupService
    caminho1 = BackupService.criar_snapshot("manual")
    # Um segundo snapshot não deve conter a pasta do primeiro
    time.sleep(1.1)
    caminho2 = BackupService.criar_snapshot("manual")
    conteudo2 = os.listdir(caminho2)
    assert all(f.endswith(".json") for f in conteudo2)
    assert "backups" not in conteudo2


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


def test_listar_backups_conta_ficheiros(ambiente_backup):
    from services.backup_service import BackupService
    BackupService.criar_snapshot("manual")
    backups = BackupService.listar_backups()
    assert backups[0]["n_ficheiros"] == 3


def test_limpar_backups_antigos_mantem_apenas_os_recentes(ambiente_backup):
    from services.backup_service import BackupService
    for i in range(5):
        BackupService.criar_snapshot(f"snap{i}")
        time.sleep(1.1)
    assert len(BackupService.listar_backups()) == 5

    removidos = BackupService.limpar_backups_antigos(manter=2)
    assert removidos == 3
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
    data_dir, _ = ambiente_backup
    caminho = BackupService.criar_snapshot("manual")
    nome_backup = os.path.basename(caminho)

    # Corrompe o ficheiro atual
    caminho_pedidos = os.path.join(data_dir, "pedidos.json")
    with open(caminho_pedidos, "w") as f:
        f.write("CORROMPIDO")

    restaurados = BackupService.restaurar_backup(nome_backup)
    assert "pedidos.json" in restaurados

    with open(caminho_pedidos) as f:
        assert f.read() == '[{"id": 5}]'


def test_restaurar_backup_inexistente_leva_erro(ambiente_backup):
    from services.backup_service import BackupService
    with pytest.raises(FileNotFoundError):
        BackupService.restaurar_backup("nao_existe_2020-01-01_000000_manual")
