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
def ambiente_resumo(db_sqlite):
    """Todos os services envolvidos (Producao, Maquina, NC) já usam SQLite —
    basta a BD isolada partilhada."""
    return {"db": db_sqlite}


def _seed_logs(ambiente, logs):
    """Insere produções de teste diretamente em SQLite (ProducaoService já
    está migrado). Cria também o código NC/ação referenciado, se algum log
    o usar, só para satisfazer a FK — a descrição real fica no catálogo
    JSON, semeado à parte via JSONManager.salvar em ambiente['nc']."""
    from database.sqlite_manager import SQLiteManager
    with SQLiteManager.conectar() as con:
        for log in logs:
            nc_cod = log.get("nc_codigo") or None
            if nc_cod:
                con.execute(
                    "INSERT OR IGNORE INTO nc_falhas (cod, descricao, tecnologia) VALUES (?, '', 'FDM')",
                    (nc_cod,),
                )
            cur = con.execute(
                "INSERT INTO producoes (data_inicio, tecnologia, maquina_nome, estado, "
                "tempo_real, tempo_estimado, nc_codigo) VALUES (?, 'FDM', ?, ?, ?, ?, ?)",
                (log.get("data_inicio", ""), log.get("maquina", ""), log.get("estado", "Em Andamento"),
                 log.get("tempo_real", ""), log.get("tempo_estimado", ""), nc_cod),
            )
            pid = cur.lastrowid
            for act_cod in log.get("acoes_aplicadas", []):
                con.execute(
                    "INSERT OR IGNORE INTO acoes_corretivas (act, acao, tecnologia) VALUES (?, '', 'FDM')",
                    (act_cod,),
                )
                con.execute(
                    "INSERT OR IGNORE INTO producao_acoes_aplicadas (producao_id, act) VALUES (?, ?)",
                    (pid, act_cod),
                )


def _seed_maquinas(ambiente, maquinas):
    from services.maquina_service import MaquinaService
    for m in maquinas:
        MaquinaService.salvar_maquina(
            m.get("id", ""), m.get("nome", ""), m.get("tech", "FDM"),
            m.get("estado", "Operacional"), m.get("manutencao", "OK"), m.get("url_img", ""),
        )


def test_resumo_diario_com_dados_mistos(tmp_path, ambiente_resumo):
    hoje = datetime.now().strftime("%Y-%m-%d")
    _seed_logs(ambiente_resumo, [
        {"id": 1, "maquina": "Bambu Lab X1C #1", "data_inicio": f"{hoje} 08:00:00",
         "estado": "Concluída", "tempo_real": "02:00"},
        {"id": 2, "maquina": "Bambu Lab X1C #2", "data_inicio": f"{hoje} 09:00:00",
         "estado": "Cancelada", "nc_codigo": "COD003", "acoes_aplicadas": []},
        {"id": 3, "maquina": "Bambu Lab P1S #1", "data_inicio": f"{hoje} 10:00:00",
         "estado": "Em Andamento", "tempo_estimado": "03:00"},
    ])
    _seed_maquinas(ambiente_resumo, [
        {"id": "EnderS1-4", "nome": "Ender S1 Pro #4", "estado": "Manutenção - Parado", "manutencao": "Troca de nozzle"},
        {"id": "X1C-1", "nome": "Bambu Lab X1C #1", "estado": "Operacional"},
    ])
    # Catálogo NC agora vive em SQLite; _seed_logs já cria o código pela FK,
    # aqui só se preenche a descrição real para o PDF a poder mostrar.
    from database.sqlite_manager import SQLiteManager
    with SQLiteManager.conectar() as con:
        con.execute("INSERT OR REPLACE INTO nc_falhas (cod, descricao, tecnologia) "
                    "VALUES ('COD003', 'Encolhimento', 'FDM')")

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
    _seed_logs(ambiente_resumo, [
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
    _seed_logs(ambiente_resumo, logs)

    from services.pdf_service import PDFService
    caminho_saida = str(tmp_path / "resumo_muitas.pdf")
    resultado = PDFService.gerar_resumo_diario(caminho_saida, data_referencia=hoje)
    assert os.path.exists(resultado)


def test_resumo_diario_caracteres_pt_nao_rebentam(tmp_path, ambiente_resumo):
    """Nomes de máquina/projeto com acentuação portuguesa não podem
    provocar UnicodeEncodeError no fpdf (fontes core usam latin-1)."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    _seed_maquinas(ambiente_resumo, [
        {"id": "M1", "nome": "Impressora Nº1 - Configuração Especial", "estado": "Manutenção - Parado", "manutencao": "Calibração"},
    ])
    from services.pdf_service import PDFService
    caminho_saida = str(tmp_path / "resumo_pt.pdf")
    resultado = PDFService.gerar_resumo_diario(caminho_saida, data_referencia=hoje)
    assert os.path.exists(resultado)
