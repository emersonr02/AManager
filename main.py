import os
import sys


# ── Executável (PyInstaller) ─────────────────────────────────────────────
# O AManager.exe fica na pasta partilhada, ao lado da pasta data/: é ela que
# config/paths.py usa como base de dados. Estas verificações só correm no
# executável; a correr com `python main.py` não fazem nada.

FICHEIROS_DE_DADOS = ("pedidos.json", "producao_i3D.json")


def _perguntar(mensagem: str) -> bool:
    """Sim/Não nativo do Windows: ainda não há janela Tk nesta altura, e criar
    uma só para a pergunta e depois a da app é instável no Tcl/Tk."""
    import ctypes
    MB_YESNO, MB_ICONWARNING, MB_DEFBUTTON2, IDYES = 0x4, 0x30, 0x100, 6
    return ctypes.windll.user32.MessageBoxW(None, mensagem, "AManager",
                                            MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2) == IDYES


def redirecionar_erros(pasta_log: str):
    """Sem consola, os erros perdiam-se: passam a ir para erros.log (local, por
    utilizador). Acima de 1 MB o log antigo passa a erros.log.1."""
    try:
        os.makedirs(pasta_log, exist_ok=True)
        log = os.path.join(pasta_log, "erros.log")
        if os.path.exists(log) and os.path.getsize(log) > 1_000_000:
            os.replace(log, log + ".1")
        sys.stdout = sys.stderr = open(log, "a", encoding="utf-8", buffering=1)
    except OSError:
        pass


def confirmar_pasta_de_dados(pasta_exe: str, perguntar=_perguntar) -> bool:
    """Um .exe copiado para fora da pasta partilhada (ex: para o ambiente de
    trabalho) criaria uma base de dados vazia e separada da equipa — pergunta
    antes de arrancar, em vez de o deixar acontecer em silêncio."""
    data = os.path.join(pasta_exe, "data")
    if any(os.path.exists(os.path.join(data, f)) for f in FICHEIROS_DE_DADOS):
        return True
    return perguntar(
        "Não encontrei pedidos nem ordens de produção em:\n\n"
        f"{data}\n\n"
        "O AManager.exe tem de ficar na pasta partilhada, ao lado da pasta \"data\". "
        "Se o copiou para o seu computador, apague a cópia e use um atalho para o da rede.\n\n"
        "Abrir mesmo assim, com uma base de dados vazia nesta pasta?")


def verificar(app) -> list:
    """`AManager.exe --verificar`: abre todos os ecrãs e gera um PDF e o CSV de
    histórico (numa pasta temporária) com os dados que estiverem ao lado do
    .exe. Confirma, na rede e com os dados reais, que o executável tem tudo o
    que precisa. Devolve os erros encontrados (lista vazia = tudo bem)."""
    import tempfile
    import traceback

    erros = []
    original = app.report_callback_exception
    # Erros dentro de callbacks do Tk não sobem até aqui: apanha-os também
    app.report_callback_exception = lambda tipo, valor, tb: erros.append(
        "".join(traceback.format_exception(tipo, valor, tb)))
    try:
        for nome in app._tab_registry:
            try:
                app.selecionar_tela(nome)
                app.update()
            except Exception:
                erros.append(f"Ecrã {nome}:\n{traceback.format_exc()}")
        app.selecionar_tela("painel")

        try:
            from services.export_service import ExportService
            from services.maquina_service import MaquinaService
            from services.pdf_service import PDFService
            from services.pedido_service import PedidoService
            from services.producao_service import ProducaoService
            producoes, pedidos = ProducaoService.obter_todos(), PedidoService.obter_todos()
            with tempfile.TemporaryDirectory() as pasta:
                ExportService.exportar_historico_csv(os.path.join(pasta, "historico.csv"), producoes, pedidos)
                if producoes:
                    ids = {str(v) for v in ProducaoService.ids_pedidos_vinculados(producoes[0])}
                    PDFService.gerar_ordem_producao(producoes[0], [p for p in pedidos if str(p.get("id")) in ids],
                                                    MaquinaService.obter_lookup_id_nome(),
                                                    os.path.join(pasta, "ordem.pdf"))
        except Exception:
            erros.append(f"PDF / exportação:\n{traceback.format_exc()}")
    finally:
        app.report_callback_exception = original
    return erros


def _concluir_verificacao(app):
    from tkinter import messagebox
    erros = verificar(app)
    app.erros_verificacao = erros
    for erro in erros:
        print(erro)
    if erros:
        print(f"VERIFICACAO: {len(erros)} problema(s)")
        messagebox.showerror("AManager — verificação",
                             f"{len(erros)} problema(s). O detalhe ficou em:\n{getattr(sys.stderr, 'name', 'erros.log')}",
                             parent=app)
    else:
        print("VERIFICACAO: OK")
        messagebox.showinfo("AManager — verificação",
                            "Tudo bem: todos os ecrãs abriram e o PDF e a exportação funcionam.", parent=app)
    app.destroy()


def main():
    if getattr(sys, "frozen", False):
        redirecionar_erros(os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "AManager"))
        # Antes de importar a app: config/paths.py cria a pasta data/ ao ser importado
        if not confirmar_pasta_de_dados(os.path.dirname(sys.executable)):
            return

    from gui.app import AppIndustrialI3D
    app = AppIndustrialI3D()
    if "--verificar" in sys.argv[1:]:
        app.after(500, lambda: _concluir_verificacao(app))
    app.mainloop()
    if getattr(app, "erros_verificacao", None):
        sys.exit(1)


if __name__ == "__main__":
    main()
