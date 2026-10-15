from datetime import datetime
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from services.pedido_service import PedidoService
from gui.dialogs.novo_pedido import JanelaNovoPedido
from gui.dialogs.editar_pedido import JanelaEditarPedido
from gui import theme

_FILTROS = {
    "Abertos": ("Pendente", "Em Andamento"),
    "Concluídos": ("Concluído", "Entregue"),
    "Cancelados": ("Cancelado",),
    "Todos": None,
}
_ESTADOS_EDITAVEIS = ["Pendente", "Em Andamento", "Concluído", "Entregue"]


def _cancelado(p):
    return p.get("ativo") is False or p.get("estado") == "Cancelado"


class PedidosTab:
    def __init__(self, parent_frame, f_padrao=None, f_titulo=None, master_app=None):
        self.parent = parent_frame
        self.master_app = master_app
        self.parent.configure(fg_color=theme.BG)
        self.construir_layout()
        self.atualizar_tabela()

    # ------------------------------------------------------------------ #
    #  LAYOUT                                                              #
    # ------------------------------------------------------------------ #
    def construir_layout(self):
        cab = theme.page_header(self.parent, "Backlog", "Pedidos")
        cab.pack(fill="x", padx=24, pady=(18, 8))
        theme.button_action(cab.acoes, text="+ Novo pedido", height=34, command=self.abrir_novo_pedido).pack(side="left")

        frm_kpi = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_kpi.pack(fill="x", padx=19, pady=(4, 8))
        self.lbl_kpi_total = theme.kpi_card(frm_kpi, "Abertos", "0")
        self.lbl_kpi_andamento = theme.kpi_card(frm_kpi, "Em andamento", "0", theme.TEAL)
        self.lbl_kpi_atrasados = theme.kpi_card(frm_kpi, "Atrasados", "0")
        self.lbl_kpi_entregues = theme.kpi_card(frm_kpi, "Concluídos / entregues", "0")

        # Filtros: separadores por estado + pesquisa livre
        frm_flt = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_flt.pack(fill="x", padx=24, pady=(0, 6))
        self.seg_filtro = theme.segmented(frm_flt, values=list(_FILTROS), command=lambda _: self.atualizar_tabela())
        self.seg_filtro.set("Abertos")
        self.seg_filtro.pack(side="left")
        self.ent_pesquisa = theme.entry(frm_flt, width=280, placeholder_text="Pesquisar código, projeto, requerente…")
        self.ent_pesquisa.pack(side="right")
        self.ent_pesquisa.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        # Ações sobre o pedido selecionado (antes só no clique direito)
        frm_acoes = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_acoes.pack(side="bottom", fill="x", padx=24, pady=(0, 16))
        self.btn_editar = theme.button_primary(frm_acoes, text="Editar pedido", height=36, width=130, command=self.abrir_edicao)
        self.btn_editar.pack(side="left", padx=(0, 8))
        self.btn_estado = theme.button_ghost(frm_acoes, text="Alterar estado", height=36, width=130, command=self.abrir_dialogo_estado)
        self.btn_estado.pack(side="left", padx=(0, 8))
        self.btn_email = theme.button_ghost(frm_acoes, text="Email de resposta", height=36, width=150, command=self.abrir_email_resposta)
        self.btn_email.pack(side="left")
        self.btn_cancelar = theme.button_danger(frm_acoes, text="Cancelar pedido", height=36, width=140, command=self.soft_delete_pedido)
        self.btn_cancelar.pack(side="right")

        frm_lista = theme.card(self.parent)
        frm_lista.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        frm_tab, self.tree_pedidos = theme.tabela(frm_lista, [
            ("id", "Pedido", 96, "w", False),
            ("prazo", "Prazo", 120, "w", False),
            ("projeto", "Projeto", 220, "w"),
            ("requerente", "Requerente", 190, "w"),
            ("tech", "Tecnologia", 90, "center", False),
            ("progresso", "Progresso", 110, "center", False),
            ("status", "Estado", 120, "w", False),
        ])
        frm_tab.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree_pedidos.bind("<Double-1>", self.abrir_edicao)
        self.tree_pedidos.bind("<Button-3>", self.mostrar_menu_contexto)
        self._atualizar_botoes = theme.ligar_a_selecao(
            self.tree_pedidos, [self.btn_editar, self.btn_estado, self.btn_email, self.btn_cancelar])

    # ------------------------------------------------------------------ #
    #  DADOS                                                               #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _texto_prazo(pedido, dias):
        data = PedidoService.normalizar_data_entrega(pedido.get("data_entrega", ""))
        if not data:
            return "—"
        data_fmt = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
        if pedido.get("estado") not in PedidoService.ESTADOS_ABERTOS or dias is None:
            return data_fmt
        if dias < 0:
            return f"{data_fmt} (atrasado)"
        if dias == 0:
            return f"{data_fmt} (hoje)"
        if dias == 1:
            return f"{data_fmt} (amanhã)"
        if dias <= 2:
            return f"{data_fmt} (em {dias} dias)"
        return data_fmt

    def atualizar_tabela(self):
        for i in self.tree_pedidos.get_children():
            self.tree_pedidos.delete(i)

        pedidos = PedidoService.obter_todos()
        filtro = _FILTROS.get(self.seg_filtro.get())
        termo = self.ent_pesquisa.get().strip().lower()

        abertos = andamento = atrasados = fechados = 0
        linhas = []
        for p in pedidos:
            estado = "Cancelado" if _cancelado(p) else p.get("estado", "Pendente")
            dias = PedidoService.dias_ate_prazo(p)
            aberto = estado in PedidoService.ESTADOS_ABERTOS
            # KPIs sobre todos os pedidos (não dependem do separador escolhido)
            if aberto:
                abertos += 1
                if estado == "Em Andamento":
                    andamento += 1
                if dias is not None and dias < 0:
                    atrasados += 1
            elif estado in PedidoService.ESTADOS_FECHADOS:
                fechados += 1

            if filtro is not None and estado not in filtro:
                continue
            projeto = f"{p.get('nr_projeto', '')} - {p.get('nome_projeto', '')}" if p.get("nome_projeto") else str(p.get("nr_projeto", ""))
            codigo = PedidoService.formatar_codigo(p.get("id"))
            if termo and termo not in " ".join([codigo, projeto, str(p.get("requerente_email", ""))]).lower():
                continue
            feitas, total = PedidoService.progresso(p)
            if estado == "Cancelado":
                tag = "tag_muted"
            elif aberto and dias is not None and dias < 0:
                tag = "tag_bad"
            elif aberto and dias is not None and dias <= 2:
                tag = "tag_warn"
            elif estado == "Em Andamento":
                tag = "tag_run"
            else:
                tag = "tag_neutral"
            linhas.append(((dias if (aberto and dias is not None) else 10**6), -int(p.get("id", 0)), (
                codigo, self._texto_prazo(p, dias), projeto, p.get("requerente_email", ""), p.get("tecnologia", "") or "—",
                f"{feitas}/{total}" if total else "—", estado,
            ), tag))

        # Abertos: o prazo mais próximo primeiro; restantes: mais recentes primeiro
        if self.seg_filtro.get() == "Abertos":
            linhas.sort(key=lambda l: (l[0], l[1]))
        for _, _, valores, tag in linhas:
            self.tree_pedidos.insert("", "end", tags=(tag,), values=valores)

        self.lbl_kpi_total.configure(text=str(abertos))
        self.lbl_kpi_andamento.configure(text=str(andamento))
        self.lbl_kpi_atrasados.configure(text=str(atrasados), text_color=theme.CRITICAL if atrasados else theme.TEXT)
        self.lbl_kpi_entregues.configure(text=str(fechados))
        self._atualizar_botoes()

    def _pedido_selecionado(self):
        sel = self.tree_pedidos.selection()
        if not sel:
            return None
        return PedidoService.obter_por_id(PedidoService.extrair_id(self.tree_pedidos.item(sel[0])["values"][0]))

    # ------------------------------------------------------------------ #
    #  AÇÕES                                                               #
    # ------------------------------------------------------------------ #
    def mostrar_menu_contexto(self, event):
        item = self.tree_pedidos.identify_row(event.y)
        if item:
            self.tree_pedidos.selection_set(item)
            menu = tk.Menu(self.parent, tearoff=0, font=("Segoe UI", 10))
            menu.add_command(label="Editar pedido", command=self.abrir_edicao)
            menu.add_command(label="Alterar estado", command=self.abrir_dialogo_estado)
            menu.add_command(label="Email de resposta", command=self.abrir_email_resposta)
            menu.add_separator()
            menu.add_command(label="Cancelar pedido", command=self.soft_delete_pedido)
            menu.post(event.x_root, event.y_root)

    def abrir_novo_pedido(self):
        JanelaNovoPedido(self.parent.winfo_toplevel(), self.atualizar_tabela)

    def abrir_edicao(self, event=None):
        pedido = self._pedido_selecionado()
        if pedido:
            JanelaEditarPedido(self.parent.winfo_toplevel(), pedido, self.atualizar_tabela)

    def abrir_dialogo_estado(self):
        pedido = self._pedido_selecionado()
        if pedido:
            self.dialogo = JanelaAlterarEstado(self.parent.winfo_toplevel(), pedido, self.atualizar_tabela)

    def abrir_email_resposta(self):
        pedido = self._pedido_selecionado()
        if pedido:
            self.dialogo = JanelaEmailResposta(self.parent.winfo_toplevel(), pedido)

    def soft_delete_pedido(self):
        pedido = self._pedido_selecionado()
        if not pedido:
            return
        codigo = PedidoService.formatar_codigo(pedido.get("id"))
        if messagebox.askyesno("Cancelar pedido",
                               f"Cancelar o pedido {codigo}?\n\nDeixa de aparecer nos pedidos abertos; "
                               "o registo fica guardado no separador Cancelados."):
            PedidoService.eliminar_pedido(pedido.get("id"))
            theme.toast(self.parent, f"Pedido {codigo} cancelado.", "info")
            self.atualizar_tabela()


class JanelaAlterarEstado(theme.Dialogo):
    def __init__(self, parent, pedido, ao_guardar):
        self.pedido = pedido
        self._ao_guardar = ao_guardar
        codigo = PedidoService.formatar_codigo(pedido.get("id"))
        feitas, total = PedidoService.progresso(pedido)
        sugerido = PedidoService.estado_sugerido(pedido)
        subtitulo = f"Progresso: {feitas}/{total} unidades produzidas." if total else ""
        if sugerido != pedido.get("estado"):
            subtitulo += f" Estado sugerido pelo progresso: {sugerido}."
        super().__init__(parent, f"Alterar estado de {codigo}", largura=440, altura=300, scroll=False,
                         subtitulo=subtitulo.strip())
        theme.rotulo_campo(self.corpo, "Novo estado").pack(anchor="w", pady=(8, 2))
        self.cmb_estado = theme.combobox(self.corpo, values=_ESTADOS_EDITAVEIS, state="readonly")
        self.cmb_estado.set(pedido.get("estado", "Pendente"))
        self.cmb_estado.pack(fill="x")

    def confirmar(self):
        PedidoService.alterar_estado(self.pedido.get("id"), self.cmb_estado.get())
        theme.toast(self, f"{PedidoService.formatar_codigo(self.pedido.get('id'))}: estado alterado para {self.cmb_estado.get()}.")
        self._ao_guardar()
        self.destroy()


class JanelaEmailResposta(theme.Dialogo):
    """Gera um texto de resposta pronto a copiar — nunca envia nada sozinho."""

    def __init__(self, parent, pedido):
        codigo = PedidoService.formatar_codigo(pedido.get("id"))
        super().__init__(parent, f"Email de resposta — {codigo}", largura=520, altura=420, texto_acao="Copiar texto",
                         scroll=False, subtitulo=f"Para {pedido.get('requerente_email', '')}. Pode editar antes de copiar.")
        feitas, total = PedidoService.progresso(pedido)
        progresso = f" ({feitas} de {total} unidades produzidas)" if total else ""
        texto = (
            "Bom dia,\n\n"
            f"O seu pedido de impressão {codigo} (projeto {pedido.get('nr_projeto', '')}) "
            f"está: {pedido.get('estado', 'Pendente')}{progresso}.\n\n"
            "Qualquer dúvida, estamos disponíveis.\n"
        )
        self.txt_email = ctk.CTkTextbox(self.corpo, fg_color=theme.SURFACE, text_color=theme.TEXT,
                                        border_color=theme.BORDER, border_width=1, font=theme.font_body(13))
        self.txt_email.pack(fill="both", expand=True)
        self.txt_email.insert("1.0", texto)

    def confirmar(self):
        self.clipboard_clear()
        self.clipboard_append(self.txt_email.get("1.0", tk.END).strip())
        theme.toast(self, "Texto copiado para a área de transferência.", "info")
        self.destroy()
