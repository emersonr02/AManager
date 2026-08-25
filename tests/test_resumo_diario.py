"""
Testes de PDFService.gerar_resumo_diario — o resumo de uma página para
arranque de turno (produções do dia, NCs, máquinas paradas).

Como o conteúdo real do PDF não é facilmente inspecionável em testes,
estes testes focam-se em: o ficheiro é gerado sem erros para vários
cenários de dados (incluindo casos vazios/extremos), e o tamanho do
ficheiro é plausível (não está vazio/corrompido).
"""
import os
import pytest
from datetime import datetime


@pytest.fixture
def ambiente_resumo(tmp_path, monkeypatch):
    from services import producao_service, maquina_service, nc_service
    from database.json_manager import JSONManager

    caminho_logs = tmp_path / "producao.json"
    caminho_maq = tmp_path / "maquinas.json"
    caminho_nc = tmp_path / "nc.json"
    caminho_acoes = tmp_path / "acoes.json"

    monkeypatch.setattr(producao_service, "ARQUIVO_LOGS", str(caminho_logs))
    monkeypatch.setattr(maquina_service, "ARQUIVO_MAQUINAS", str(caminho_maq))
    monkeypatch.setattr(nc_service, "ARQUIVO_NC_FALHAS", str(caminho_nc))
    monkeypatch.setattr(nc_service, "ARQUIVO_ACOES", str(caminho_acoes))

    JSONManager.salvar([], str(caminho_logs))
    JSONManager.salvar([], str(caminho_maq))
    JSONManager.salvar([], str(caminho_nc))
    JSONManager.salvar([], str(caminho_acoes))

    return {
        "logs": str(caminho_logs), "maquinas": str(caminho_maq),
        "nc": str(caminho_nc), "acoes": str(caminho_acoes),
    }


def _seed_logs(caminho, logs):
    from database.json_manager import JSONManager
    JSONManager.salvar(logs, caminho)


def _seed_maquinas(caminho, maquinas):
    from database.json_manager import JSONManager
    JSONManager.salvar(maquinas, caminho)


def test_resumo_diario_com_dados_mistos(tmp_path, ambiente_resumo):
    hoje = datetime.now().strftime("%Y-%m-%d")
    _seed_logs(ambiente_resumo["logs"], [
        {"id": 1, "maquina": "Bambu Lab X1C #1", "data_inicio": f"{hoje} 08:00:00",
         "estado": "Concluída", "tempo_real": "02:00"},
        {"id": 2, "maquina": "Bambu Lab X1C #2", "data_inicio": f"{hoje} 09:00:00",
         "estado": "Cancelada", "nc_codigo": "COD003", "acoes_aplicadas": []},
        {"id": 3, "maquina": "Bambu Lab P1S #1", "data_inicio": f"{hoje} 10:00:00",
         "estado": "Em Andamento", "tempo_estimado": "03:00"},
    ])
    _seed_maquinas(ambiente_resumo["maquinas"], [
        {"id": "EnderS1-4", "nome": "Ender S1 Pro #4", "estado": "Manutenção - Parado", "manutencao": "Troca de nozzle"},
        {"id": "X1C-1", "nome": "Bambu Lab X1C #1", "estado": "Operacional"},
    ])
    from database.json_manager import JSONManager
    JSONManager.salvar([{"cod": "COD003", "descricao": "Encolhimento", "tecnologia": "FDM"}], ambiente_resumo["nc"])

    from services.pdf_service import PDFService
    caminho_saida = str(tmp_path / "resumo.pdf")
    resultado = PDFService.gerar_resumo_diario(caminho_saida, data_referencia=hoje)

    assert resultado == caminho_saida
    assert os.path.exists(caminho_saida)
    assert os.path.getsize(caminho_saida) > 1000  # PDF plausível, não vazio/corrompido


def test_resumo_diario_dia_completamente_vazio(tmp_path, ambiente_resumo):
    """Sem nenhuma produção, NC ou máquina parada — não deve rebentar."""
    from services.pdf_service import PDFService
    caminho_saida = str(tmp_path / "resumo_vazio.pdf")
    resultado = PDFService.gerar_resumo_diario(caminho_saida, data_referencia="2020-01-01")

    assert os.path.exists(resultado)
    assert os.path.getsize(resultado) > 500


def test_resumo_diario_usa_hoje_por_omissao(tmp_path, ambiente_resumo):
    """Sem indicar data_referencia, deve usar a data de hoje."""
    from services.pdf_service import PDFService
    caminho_saida = str(tmp_path / "resumo_hoje.pdf")
    resultado = PDFService.gerar_resumo_diario(caminho_saida)
    assert os.path.exists(resultado)


def test_resumo_diario_producoes_de_outros_dias_nao_contam_nos_kpis(tmp_path, ambiente_resumo):
    """KPIs do dia só devem contar produções cuja data_inicio é do dia de
    referência — produções antigas ainda 'Em Andamento' aparecem na secção
    'Em Curso' mas não nos KPIs de 'produções concluídas hoje' etc."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    _seed_logs(ambiente_resumo["logs"], [
        {"id": 1, "maquina": "X", "data_inicio": "2020-01-01 08:00:00", "estado": "Concluída"},
        {"id": 2, "maquina": "Y", "data_inicio": "2020-01-01 09:00:00", "estado": "Em Andamento", "tempo_estimado": "10:00"},
    ])
    from services.pdf_service import PDFService
    caminho_saida = str(tmp_path / "resumo.pdf")
    # Não deve rebentar mesmo que nenhuma produção seja "de hoje"
    resultado = PDFService.gerar_resumo_diario(caminho_saida, data_referencia=hoje)
    assert os.path.exists(resultado)


def test_resumo_diario_muitas_producoes_em_curso_trunca_lista(tmp_path, ambiente_resumo):
    """Mais de 15 produções em curso não devem rebentar o PDF (a função
    trunca a listagem e acrescenta um resumo do restante)."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    logs = [
        {"id": i, "maquina": f"Máquina {i}", "data_inicio": f"{hoje} 08:00:00", "estado": "Em Andamento"}
        for i in range(25)
    ]
    _seed_logs(ambiente_resumo["logs"], logs)

    from services.pdf_service import PDFService
    caminho_saida = str(tmp_path / "resumo_muitas.pdf")
    resultado = PDFService.gerar_resumo_diario(caminho_saida, data_referencia=hoje)
    assert os.path.exists(resultado)


def test_resumo_diario_caracteres_pt_nao_rebentam(tmp_path, ambiente_resumo):
    """Nomes de máquina/projeto com acentuação portuguesa não podem
    provocar UnicodeEncodeError no fpdf (fontes core usam latin-1)."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    _seed_maquinas(ambiente_resumo["maquinas"], [
        {"id": "M1", "nome": "Impressora Nº1 - Configuração Especial", "estado": "Manutenção - Parado", "manutencao": "Calibração"},
    ])
    from services.pdf_service import PDFService
    caminho_saida = str(tmp_path / "resumo_pt.pdf")
    resultado = PDFService.gerar_resumo_diario(caminho_saida, data_referencia=hoje)
    assert os.path.exists(resultado)
