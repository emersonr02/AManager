from conftest import seed_nc_falhas, seed_acoes_corretivas
from services.nc_service import NCService


def test_garantir_arquivos_e_idempotente(arquivos_nc):
    """Com SQLite, garantir_arquivos() garante o esquema em vez de criar
    ficheiros vazios — deve poder ser chamado sem efeitos colaterais."""
    NCService.garantir_arquivos()
    NCService.garantir_arquivos()
    assert NCService.obter_nc_por_tecnologia("FDM") == []


def test_obter_nc_por_tecnologia_filtra_e_formata(arquivos_nc):
    seed_nc_falhas([
        {"cod": "COD001", "descricao": "Obstrução do bico", "tecnologia": "FDM"},
        {"cod": "COD002", "descricao": "Falha de resina", "tecnologia": "SLA"},
    ])

    resultado = NCService.obter_nc_por_tecnologia("FDM")

    assert resultado == ["COD001 - Obstrução do bico"]


def test_obter_acoes_por_cod_filtra_por_codigo_aplicavel(arquivos_nc):
    seed_nc_falhas([
        {"cod": "COD001", "descricao": "Obstrução", "tecnologia": "FDM"},
        {"cod": "COD002", "descricao": "Resina", "tecnologia": "SLA"},
    ])
    seed_acoes_corretivas([
        {"act": "ACT001", "acao": "Limpeza do nozzle", "codigos_aplicaveis": ["COD001"]},
        {"act": "ACT002", "acao": "Troca de resina", "codigos_aplicaveis": ["COD002"]},
    ])

    resultado = NCService.obter_acoes_por_cod("COD001")

    assert len(resultado) == 1
    assert resultado[0]["acao"] == "Limpeza do nozzle"


def test_obter_acoes_por_cod_sem_correspondencia_devolve_lista_vazia(arquivos_nc):
    seed_nc_falhas([{"cod": "COD001", "descricao": "Obstrução", "tecnologia": "FDM"}])
    seed_acoes_corretivas([
        {"act": "ACT001", "acao": "Limpeza do nozzle", "codigos_aplicaveis": ["COD001"]},
    ])

    assert NCService.obter_acoes_por_cod("COD999") == []


def test_obter_acoes_por_cod_vazio_devolve_lista_vazia(arquivos_nc):
    assert NCService.obter_acoes_por_cod("") == []
    assert NCService.obter_acoes_por_cod(None) == []


def test_obter_acoes_devolve_etapas_desserializadas(arquivos_nc):
    """As etapas são guardadas como JSON numa coluna — devem voltar como
    lista Python, não como string."""
    seed_nc_falhas([{"cod": "COD001", "descricao": "Obstrução", "tecnologia": "FDM"}])
    seed_acoes_corretivas([
        {"act": "ACT001", "acao": "Limpeza", "codigos_aplicaveis": ["COD001"],
         "etapas": ["Passo 1", "Passo 2"]},
    ])

    resultado = NCService.obter_acoes_por_cod("COD001")
    assert resultado[0]["etapas"] == ["Passo 1", "Passo 2"]


def test_obter_descricao_encontra_pelo_codigo(arquivos_nc):
    seed_nc_falhas([
        {"cod": "COD001", "descricao": "Obstrução do bico", "tecnologia": "FDM"},
    ])

    assert NCService.obter_descricao("COD001") == "Obstrução do bico"


def test_obter_descricao_sem_correspondencia_devolve_vazio(arquivos_nc):
    assert NCService.obter_descricao("COD999") == ""
