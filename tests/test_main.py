"""Arranque do executável (main.py): aviso quando o .exe não está ao lado dos
dados, log de erros sem consola e o modo --verificar."""
import sys

import main
from services.pedido_service import PedidoService
from services.producao_service import ProducaoService


def test_com_dados_ao_lado_do_exe_arranca_sem_perguntar(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "producao_i3D.json").write_text("[]", encoding="utf-8")

    assert main.confirmar_pasta_de_dados(str(tmp_path), perguntar=lambda m: _nao_devia_perguntar(m)) is True


def test_sem_dados_pergunta_e_respeita_a_resposta(tmp_path):
    perguntas = []
    assert main.confirmar_pasta_de_dados(str(tmp_path), perguntar=lambda m: perguntas.append(m) or False) is False
    assert str(tmp_path / "data") in perguntas[0]
    assert not (tmp_path / "data").exists()   # "Não" não cria a pasta

    assert main.confirmar_pasta_de_dados(str(tmp_path), perguntar=lambda m: True) is True


def test_erros_vao_para_um_log_que_roda_acima_de_1mb(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdout", sys.stdout)
    monkeypatch.setattr(sys, "stderr", sys.stderr)
    log = tmp_path / "AManager" / "erros.log"
    log.parent.mkdir()
    log.write_text("x" * 1_000_001, encoding="utf-8")

    main.redirecionar_erros(str(log.parent))
    print("erro de teste", file=sys.stderr)
    sys.stderr.close()

    assert (tmp_path / "AManager" / "erros.log.1").stat().st_size > 1_000_000
    assert log.read_text(encoding="utf-8") == "erro de teste\n"


def test_verificar_abre_todos_os_ecras_e_gera_pdf(gui_arquivos, arquivos_nc, app_sessao):
    pedido = PedidoService.criar_pedido(requerente_email="a@x.pt", nr_projeto="1", nome_projeto="P", tecnologia="FDM",
                                        data_entrega="2026-12-01", link_arquivos="", observacoes="",
                                        pecas=[{"pn": "A", "material": "PLA", "qtd_solicitada": 2, "qtd_produzida": 0}])
    ProducaoService.criar_producao(tecnologia="FDM", maquina="X1", tempo_estimado="01:00",
                                   pedidos_vinculados=[pedido["id"]], operador="t")

    assert main.verificar(app_sessao) == []
    assert set(app_sessao._tab_registry) <= set(app_sessao._uis)


def test_verificar_aponta_o_ecra_que_falha(gui_arquivos, arquivos_nc, app_sessao, monkeypatch):
    app_sessao.selecionar_tela("analytics")

    def falha():
        raise RuntimeError("matplotlib em falta")
    monkeypatch.setattr(app_sessao._uis["analytics"], "atualizar_tabela", falha)

    erros = main.verificar(app_sessao)

    assert len(erros) == 1 and "analytics" in erros[0] and "matplotlib em falta" in erros[0]


def _nao_devia_perguntar(mensagem):
    raise AssertionError(f"não devia perguntar: {mensagem}")
