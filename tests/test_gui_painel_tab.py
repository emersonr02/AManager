from datetime import datetime, timedelta

from database.json_manager import JSONManager
from services.maquina_service import MaquinaService
from services.manutencao_service import ManutencaoService
from services.pedido_service import PedidoService
from services.producao_service import ProducaoService
from gui.painel_tab import PainelTab


def _etiquetas(tab):
    return [etiqueta for _, etiqueta, _, _ in tab.itens_atencao]


def _pedido(prazo_dias, estado="Pendente"):
    p = PedidoService.criar_pedido(
        requerente_email="a@x.com", nr_projeto="100200", nome_projeto="P", tecnologia="FDM",
        data_entrega=(datetime.now() + timedelta(days=prazo_dias)).strftime("%Y-%m-%d"),
        link_arquivos="", observacoes="", pecas=[{"pn": "A", "material": "PLA", "qtd_solicitada": 1, "qtd_produzida": 0}],
    )
    if estado != "Pendente":
        PedidoService.alterar_estado(p["id"], estado)
    return p


def test_painel_vazio_nao_assinala_nada(gui_arquivos, ctk_root):
    tab = PainelTab(ctk_root)

    assert tab.itens_atencao == []
    assert tab.lbl_kpi_atencao.cget("text") == "0"
    assert tab.lbl_kpi_em_curso.cget("text") == "0"


def test_em_curso_lista_ordens_abertas(gui_arquivos, ctk_root):
    ProducaoService.criar_producao(tecnologia="FDM", maquina="X1", tempo_estimado="02:00",
                                   pedidos_vinculados=[], operador="t")
    tab = PainelTab(ctk_root)

    assert tab.lbl_kpi_em_curso.cget("text") == "1"
    assert len(tab.tree_em_curso.get_children()) == 1


def test_pedido_atrasado_e_prazo_proximo_requerem_atencao(gui_arquivos, ctk_root):
    _pedido(-3)                        # atrasado
    _pedido(1)                         # entrega amanhã
    _pedido(20)                        # longe — não assinala
    _pedido(-3, estado="Concluído")    # fechado — não assinala

    tab = PainelTab(ctk_root)

    assert sorted(_etiquetas(tab)) == ["Atrasado", "Prazo"]
    assert tab.itens_atencao[0][0] == "bad"   # o mais grave primeiro


def test_maquina_parada_requer_atencao_mas_desativada_nao(gui_arquivos, ctk_root):
    MaquinaService.salvar_maquina(mid="M1", nome="Parada", tech="FDM", estado="Manutenção - Parado", manutencao="Trocar bico")
    MaquinaService.salvar_maquina(mid="M2", nome="Antiga", tech="FDM", estado="Desativado", manutencao="OK")

    tab = PainelTab(ctk_root)

    assert _etiquetas(tab) == ["Parada"]
    assert "Trocar bico" in tab.itens_atencao[0][2]


def test_manutencao_atrasada_requer_atencao(gui_arquivos, ctk_root):
    MaquinaService.salvar_maquina(mid="M1", nome="Printer 1", tech="FDM", estado="Operacional", manutencao="OK", modelo="X")
    tarefa = ManutencaoService.criar_tarefa(modelo="X", nome="Limpeza", frequencia_dias=10)
    JSONManager.salvar([{
        "id": 1, "tarefa_id": tarefa["id"], "maquina_id": "M1", "operador": "a", "notas": "",
        "data_realizacao": (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"),
    }], gui_arquivos["manutencoes"])

    tab = PainelTab(ctk_root)

    assert _etiquetas(tab) == ["Manutenção"]


def test_nc_de_hoje_sem_acao_requer_atencao(gui_arquivos, ctk_root):
    p = ProducaoService.criar_producao(tecnologia="FDM", maquina="X1", tempo_estimado="02:00",
                                       pedidos_vinculados=[], operador="t")
    p.update({"estado": "Cancelada", "nc_codigo": "COD001", "acoes_aplicadas": []})
    ProducaoService.atualizar_producao(p)

    tab = PainelTab(ctk_root)

    assert _etiquetas(tab) == ["NC"]


def test_atalho_abrir_navega_para_o_ecra_certo(gui_arquivos, ctk_root):
    chamadas = []
    app_falsa = type("AppFalsa", (), {"selecionar_tela": lambda self, nome: chamadas.append(nome)})()
    tab = PainelTab(ctk_root, master_app=app_falsa)

    tab._ir("manutencao")

    assert chamadas == ["manutencao"]
