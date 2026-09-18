from database.json_manager import JSONManager
from services.nc_service import NCService


def test_garantir_arquivos_cria_ficheiros_vazios_se_nao_existirem(arquivos_nc):
    caminho_falhas, caminho_acoes = arquivos_nc

    NCService.garantir_arquivos()

    assert JSONManager.carregar(caminho_falhas) == []
    assert JSONManager.carregar(caminho_acoes) == []


def test_obter_nc_por_tecnologia_filtra_e_formata(arquivos_nc):
    caminho_falhas, _ = arquivos_nc
    JSONManager.salvar([
        {"cod": "COD001", "descricao": "Obstrução do bico", "tecnologia": "FDM"},
        {"cod": "COD002", "descricao": "Falha de resina", "tecnologia": "SLA"},
    ], caminho_falhas)

    resultado = NCService.obter_nc_por_tecnologia("FDM")

    assert resultado == ["COD001 - Obstrução do bico"]


def test_obter_acoes_por_cod_filtra_por_codigo_aplicavel(arquivos_nc):
    _, caminho_acoes = arquivos_nc
    JSONManager.salvar([
        {"act": "ACT001", "acao": "Limpeza do nozzle", "codigos_aplicaveis": ["COD001"]},
        {"act": "ACT002", "acao": "Troca de resina", "codigos_aplicaveis": ["COD002"]},
    ], caminho_acoes)

    resultado = NCService.obter_acoes_por_cod("COD001")

    assert len(resultado) == 1
    assert resultado[0]["acao"] == "Limpeza do nozzle"


def test_obter_acoes_por_cod_sem_correspondencia_devolve_lista_vazia(arquivos_nc):
    _, caminho_acoes = arquivos_nc
    JSONManager.salvar([
        {"act": "ACT001", "acao": "Limpeza do nozzle", "codigos_aplicaveis": ["COD001"]},
    ], caminho_acoes)

    assert NCService.obter_acoes_por_cod("COD999") == []


def test_obter_descricao_encontra_pelo_codigo(arquivos_nc):
    caminho_falhas, _ = arquivos_nc
    JSONManager.salvar([
        {"cod": "COD001", "descricao": "Obstrução do bico", "tecnologia": "FDM"},
    ], caminho_falhas)

    assert NCService.obter_descricao("COD001") == "Obstrução do bico"


def test_obter_descricao_sem_correspondencia_devolve_vazio(arquivos_nc):
    assert NCService.obter_descricao("COD999") == ""
