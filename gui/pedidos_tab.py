import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import os
from database.json_manager import JSONManager
from config.paths import ARQUIVO_PEDIDOS
from services.pedido_service import PedidoService
from gui.dialogs.novo_pedido import JanelaNovoPedido
from gui.dialogs.editar_pedido import JanelaEditarPedido
from gui.dialogs.gestao_projetos_materiais import JanelaGestaoProjetosMateriais
from gui import theme

_VARIANTE_ESTADO = {
    "Entregue": "ok", "Concluído": "ok",
    "Em Andamento": "run",
    "Cancelado": "bad",
    "Pendente": "neutral",
}


class PedidosTab:
    def __init__(self, parent_frame, f_padrao, f_titulo, master_app=None):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.f_titulo = f_titulo
        self.master_app = master_app

        self.parent.configure(fg_color=theme.BG)

        self.construir_layout()
        self.atualizar_tabela()

    def construir_layout(self):
        # 1. HEADER
        theme.page_header(self.parent, "Backlog", "Gestão de Pedidos").pack(fill="x", padx=24, pady=(22, 10))

        frm_acoes_header = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_acoes_header.pack(fill="x", padx=24, pady=(0, 10))
        theme.button_action(frm_acoes_header, text="+ Novo Pedido", command=self.abrir_novo_pedido).pack(side="right")
        theme.button_ghost(frm_acoes_header, text="Gerir Projetos / Materiais", command=self.abrir_gestao_projetos_materiais).pack(side="right", padx=(0, 10))

        # 2. CARDS DE KPI
        frm_kpi = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_kpi.pack(fill="x", padx=24, pady=10)

        self.lbl_kpi_total = theme.kpi_card(frm_kpi, "Total Ativos", "0")
        self.lbl_kpi_andamento = theme.kpi_card(frm_kpi, "Em Andamento", "0", theme.TEAL)
        self.lbl_kpi_entregues = theme.kpi_card(frm_kpi, "Entregues", "0", theme.SUCCESS)

        # 3. ÁREA DA TABELA
        frm_lista = ctk.CTkFrame(self.parent, fg_color=theme.SURFACE, corner_radius=theme.RADIUS_M, border_width=1, border_color=theme.BORDER)
        frm_lista.pack(fill="both", expand=True, padx=24, pady=(5, 18))

        # TABELA
        cols = ("id", "data", "requerente", "projeto", "status", "tech")
        self.tree_pedidos = ttk.Treeview(frm_lista, columns=cols, show="headings", style="Custom.Treeview")

        cabecalhos = ["ID", "DATA", "REQUERENTE", "PROJETO", "STATUS", "TECH"]
        anchors = {"id": "center", "data": "center", "requerente": "w", "projeto": "w", "status": "w", "tech": "center"}
        for c, h in zip(cols, cabecalhos):
            self.tree_pedidos.heading(c, text=h, anchor=anchors[c])

        self.tree_pedidos.column("id", width=95, anchor="center")
        self.tree_pedidos.column("data", width=90, anchor="center")
        self.tree_pedidos.column("requerente", width=180, anchor="w")
        self.tree_pedidos.column("projeto", width=220, anchor="w")
        self.tree_pedidos.column("status", width=130, anchor="w")
        self.tree_pedidos.column("tech", width=70, anchor="center")

        # EVENTOS: Duplo clique para editar / Clique direito para menu CRUD
        self.tree_pedidos.bind("<Double-1>", self.abrir_edicao)
        self.tree_pedidos.bind("<Button-3>", self.mostrar_menu_contexto)

        sb_ped = ttk.Scrollbar(frm_lista, orient="vertical", command=self.tree_pedidos.yview)
        self.tree_pedidos.configure(yscrollcommand=sb_ped.set)
        sb_ped.pack(fill="y", side="right", pady=10, padx=(0, 5))
        self.tree_pedidos.pack(fill="both", expand=True, side="left", padx=10, pady=10)

        self.configurar_estilo_tabela()

        # Criado depois da scrollbar: precisa de "envolver" o yscrollcommand já
        # ligado ao sb_ped.set, para saber repor as pills sempre que a vista faz scroll.
        self.status_pills = theme.TreeviewPillColumn(self.tree_pedidos, "status")

    def configurar_estilo_tabela(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Custom.Treeview", background=theme.SURFACE[0], foreground=theme.TEXT[0], rowheight=30, fieldbackground=theme.SURFACE[0], borderwidth=0)
        style.configure("Custom.Treeview.Heading", background=theme.SURFACE_ALT[0], foreground=theme.TEXT_MUTED[0], borderwidth=0)
        style.map("Custom.Treeview", background=[("selected", theme.ACCENT[0])], foreground=[("selected", "white")])

    def atualizar_tabela(self):
        for i in self.tree_pedidos.get_children(): self.tree_pedidos.delete(i)
        
        pedidos = JSONManager.carregar(ARQUIVO_PEDIDOS) if os.path.exists(ARQUIVO_PEDIDOS) else []
        
        total_ativos, andamento, entregues = 0, 0, 0
        
        pill_dados = {}

        for p in pedidos:
            # SOFT DELETE: Ignora pedidos marcados como inativos ou cancelados
            if p.get("ativo") is False or p.get("estado") == "Cancelado":
                continue

            status = p.get("estado", "Pendente")

            total_ativos += 1
            if status == "Em Andamento": andamento += 1
            if status in ["Entregue", "Concluído"]: entregues += 1

            item_id = self.tree_pedidos.insert("", "end", values=(
                PedidoService.formatar_codigo(p.get("id")), p.get("data_pedido"), p.get("requerente_email"),
                p.get("nr_projeto"), status, p.get("tecnologia")
            ))
            pill_dados[item_id] = (status, _VARIANTE_ESTADO.get(status, "neutral"))

        self.lbl_kpi_total.configure(text=str(total_ativos))
        self.lbl_kpi_andamento.configure(text=str(andamento))
        self.lbl_kpi_entregues.configure(text=str(entregues))
        self.status_pills.definir_dados(pill_dados)

    def mostrar_menu_contexto(self, event):
        item = self.tree_pedidos.identify_row(event.y)
        if item:
            self.tree_pedidos.selection_set(item)
            menu = tk.Menu(self.parent, tearoff=0, font=("Segoe UI", 10))
            menu.add_command(label="✏️ Editar Pedido", command=self.abrir_edicao)
            menu.add_command(label="🔄 Alterar Estado", command=self.abrir_dialogo_estado)
            menu.add_command(label="📧 Copiar Email de Resposta", command=self.abrir_email_resposta)
            menu.add_separator()
            menu.add_command(label="🗑️ Eliminar (Soft Delete)", command=self.soft_delete_pedido)
            menu.post(event.x_root, event.y_root)

    def abrir_email_resposta(self):
        """Gera um texto de resposta pronto a copiar — nunca envia nada sozinho."""
        sel = self.tree_pedidos.selection()
        if not sel: return
        vals = self.tree_pedidos.item(sel[0])['values']
        codigo, requerente, estado = vals[0], vals[2], vals[4]

        texto = (
            "Bom dia,\n\n"
            f"O seu pedido de impressão ID: {codigo} está: {estado}.\n\n"
            "Qualquer dúvida, estamos disponíveis.\n\n"
        )

        top = ctk.CTkToplevel(self.parent.winfo_toplevel())
        top.title(f"Email de Resposta - {codigo}")
        top.geometry("480x360")
        top.configure(fg_color=theme.BG)
        top.transient(self.parent.winfo_toplevel())
        top.grab_set()

        ctk.CTkLabel(top, text=f"Resposta para {requerente}", font=theme.font_display(14), text_color=theme.ACCENT).pack(pady=(15, 2), padx=20, anchor="w")
        ctk.CTkLabel(top, text="Pode editar o texto antes de copiar.", font=theme.font_body(11), text_color=theme.TEXT_MUTED).pack(padx=20, anchor="w")

        txt_email = ctk.CTkTextbox(top, width=440, height=220, fg_color=theme.SURFACE_ALT, text_color=theme.TEXT, border_color=theme.BORDER, border_width=1)
        txt_email.pack(padx=20, pady=10, fill="both", expand=True)
        txt_email.insert("1.0", texto)

        def copiar():
            top.clipboard_clear()
            top.clipboard_append(txt_email.get("1.0", tk.END).strip())
            top.update()
            messagebox.showinfo("Copiado", "Texto copiado para a área de transferência.")

        theme.button_primary(top, text="Copiar para a Área de Transferência", command=copiar).pack(pady=(0, 15), padx=20, fill="x")

    def abrir_novo_pedido(self):
        JanelaNovoPedido(self.parent.winfo_toplevel(), self.atualizar_tabela)

    def abrir_gestao_projetos_materiais(self):
        JanelaGestaoProjetosMateriais(self.parent.winfo_toplevel())

    def abrir_edicao(self, event=None):
        sel = self.tree_pedidos.selection()
        if not sel: return
        id_ped = PedidoService.extrair_id(self.tree_pedidos.item(sel[0])['values'][0])

        pedidos = JSONManager.carregar(ARQUIVO_PEDIDOS)
        for p in pedidos:
            if p.get("id") == id_ped:
                JanelaEditarPedido(self.parent.winfo_toplevel(), p, self.atualizar_tabela)
                break

    def abrir_dialogo_estado(self):
        sel = self.tree_pedidos.selection()
        if not sel: return
        codigo = self.tree_pedidos.item(sel[0])['values'][0]
        id_ped = PedidoService.extrair_id(codigo)
        status_atual = self.tree_pedidos.item(sel[0])['values'][4]

        top = ctk.CTkToplevel(self.parent.winfo_toplevel())
        top.title(f"Alterar Estado - Pedido #{codigo}")
        top.geometry("360x210")
        top.configure(fg_color=theme.BG)
        top.transient(self.parent.winfo_toplevel())
        top.grab_set()

        ctk.CTkLabel(top, text="Novo Estado do Pedido:", font=theme.font_body(12, "bold"), text_color=theme.TEXT).pack(pady=(20, 10))

        cmb_estado = theme.combobox(top, values=["Pendente", "Em Andamento", "Concluído", "Entregue"], width=200, state="readonly")
        cmb_estado.set(status_atual)
        cmb_estado.pack(pady=10)

        def guardar_estado():
            PedidoService.alterar_estado(id_ped, cmb_estado.get())
            self.atualizar_tabela()
            top.destroy()

        theme.button_primary(top, text="GUARDAR", command=guardar_estado).pack(pady=10)

    def soft_delete_pedido(self):
        sel = self.tree_pedidos.selection()
        if not sel: return
        codigo = self.tree_pedidos.item(sel[0])['values'][0]
        id_ped = PedidoService.extrair_id(codigo)

        if messagebox.askyesno("Confirmar Eliminação", f"Tem a certeza que deseja eliminar o Pedido #{codigo}?\n(O registo será mantido na base de dados por segurança)."):
            PedidoService.eliminar_pedido(id_ped)
            self.atualizar_tabela()