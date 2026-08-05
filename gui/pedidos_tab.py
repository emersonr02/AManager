import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import os
from database.json_manager import JSONManager
from config.paths import ARQUIVO_PEDIDOS
from gui.dialogs.novo_pedido import JanelaNovoPedido
from gui.dialogs.editar_pedido import JanelaEditarPedido

class PedidosTab:
    def __init__(self, parent_frame, f_padrao, f_titulo, master_app=None):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.f_titulo = f_titulo
        self.master_app = master_app
        
        self.parent.configure(fg_color="#f0f2f5")
        
        self.construir_layout()
        self.atualizar_tabela()

    def construir_layout(self):
        # 1. HEADER
        frm_header = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(frm_header, text="Gestão de Pedidos", font=ctk.CTkFont(size=22, weight="bold"), text_color="#1f538d").pack(side="left")
        ctk.CTkButton(frm_header, text="+ Novo Pedido", fg_color="#28a745", hover_color="#218838", text_color="white", font=self.f_padrao, command=self.abrir_novo_pedido).pack(side="right")

        # 2. CARDS DE KPI
        frm_kpi = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_kpi.pack(fill="x", padx=20, pady=10)
        
        self.lbl_kpi_total = self.criar_card_kpi(frm_kpi, "📋 Total Ativos", "0", 0)
        self.lbl_kpi_andamento = self.criar_card_kpi(frm_kpi, "⏳ Em Andamento", "0", 1)
        self.lbl_kpi_entregues = self.criar_card_kpi(frm_kpi, "✅ Entregues", "0", 2)

        # 3. ÁREA DA TABELA
        frm_lista = ctk.CTkFrame(self.parent, fg_color="white", corner_radius=10)
        frm_lista.pack(fill="both", expand=True, padx=20, pady=20)

        # TABELA
        cols = ("id", "data", "requerente", "projeto", "status", "tech")
        self.tree_pedidos = ttk.Treeview(frm_lista, columns=cols, show="headings", style="Custom.Treeview")
        
        cabecalhos = ["ID", "DATA", "REQUERENTE", "PROJETO", "STATUS", "TECH"]
        for c, h in zip(cols, cabecalhos): 
            self.tree_pedidos.heading(c, text=h)
            
        self.tree_pedidos.column("id", width=50, anchor="center")
        self.tree_pedidos.column("data", width=100, anchor="center")
        self.tree_pedidos.column("requerente", width=150, anchor="w")
        self.tree_pedidos.column("projeto", width=200, anchor="w")
        self.tree_pedidos.column("status", width=120, anchor="center")
        self.tree_pedidos.column("tech", width=80, anchor="center")

        # EVENTOS: Duplo clique para editar / Clique direito para menu CRUD
        self.tree_pedidos.bind("<Double-1>", self.abrir_edicao)
        self.tree_pedidos.bind("<Button-3>", self.mostrar_menu_contexto)

        sb_ped = ttk.Scrollbar(frm_lista, orient="vertical", command=self.tree_pedidos.yview)
        self.tree_pedidos.configure(yscrollcommand=sb_ped.set)
        sb_ped.pack(fill="y", side="right", pady=10)
        self.tree_pedidos.pack(fill="both", expand=True, side="left", padx=10, pady=10)

        self.configurar_estilo_tabela()

    def criar_card_kpi(self, parent, titulo, valor, col):
        card = ctk.CTkFrame(parent, fg_color="white", corner_radius=10, height=100)
        card.pack(side="left", fill="x", expand=True, padx=5)
        card.pack_propagate(False)
        
        ctk.CTkLabel(card, text=titulo, text_color="gray20", font=ctk.CTkFont(family="Arial", size=13, weight="bold")).pack(anchor="w", padx=15, pady=(15, 0))
        lbl_valor = ctk.CTkLabel(card, text=valor, text_color="#1f538d", font=ctk.CTkFont(size=32, weight="bold"))
        lbl_valor.pack(anchor="w", padx=15, pady=5)
        return lbl_valor

    def configurar_estilo_tabela(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Custom.Treeview", background="white", foreground="black", rowheight=30, fieldbackground="white", borderwidth=0)
        style.configure("Custom.Treeview.Heading", background="#f0f2f5", foreground="gray30", font=("Arial", 11, "bold"), borderwidth=0)
        style.map("Custom.Treeview", background=[("selected", "#1f538d")], foreground=[("selected", "white")])

    def atualizar_tabela(self):
        for i in self.tree_pedidos.get_children(): self.tree_pedidos.delete(i)
        
        pedidos = JSONManager.carregar(ARQUIVO_PEDIDOS) if os.path.exists(ARQUIVO_PEDIDOS) else []
        
        total_ativos, andamento, entregues = 0, 0, 0
        
        for p in pedidos:
            # SOFT DELETE: Ignora pedidos marcados como inativos ou cancelados
            if p.get("ativo") is False or p.get("estado", p.get("status")) == "Cancelado":
                continue
                
            status = p.get("estado", p.get("status", "Pendente"))
            
            total_ativos += 1
            if status == "Em Andamento": andamento += 1
            if status in ["Entregue", "Concluído"]: entregues += 1
            
            self.tree_pedidos.insert("", "end", values=(
                p.get("id", p.get("id_pedido")), p.get("data_pedido"), p.get("requerente_email", p.get("requerente")), 
                p.get("nr_projeto", p.get("projeto")), status, p.get("tecnologia")
            ))
            
        self.lbl_kpi_total.configure(text=str(total_ativos))
        self.lbl_kpi_andamento.configure(text=str(andamento))
        self.lbl_kpi_entregues.configure(text=str(entregues))

    def mostrar_menu_contexto(self, event):
        item = self.tree_pedidos.identify_row(event.y)
        if item:
            self.tree_pedidos.selection_set(item)
            menu = tk.Menu(self.parent, tearoff=0, font=("Arial", 10))
            menu.add_command(label="✏️ Editar Pedido", command=self.abrir_edicao)
            menu.add_command(label="🔄 Alterar Estado", command=self.abrir_dialogo_estado)
            menu.add_separator()
            menu.add_command(label="🗑️ Eliminar (Soft Delete)", command=self.soft_delete_pedido)
            menu.post(event.x_root, event.y_root)

    def abrir_novo_pedido(self):
        JanelaNovoPedido(self.parent.winfo_toplevel(), self.atualizar_tabela)

    def abrir_edicao(self, event=None):
        sel = self.tree_pedidos.selection()
        if not sel: return
        id_ped = self.tree_pedidos.item(sel[0])['values'][0]
        
        pedidos = JSONManager.carregar(ARQUIVO_PEDIDOS)
        for p in pedidos:
            if p.get("id", p.get("id_pedido")) == id_ped:
                JanelaEditarPedido(self.parent.winfo_toplevel(), p, self.atualizar_tabela)
                break

    def abrir_dialogo_estado(self):
        sel = self.tree_pedidos.selection()
        if not sel: return
        id_ped = self.tree_pedidos.item(sel[0])['values'][0]
        status_atual = self.tree_pedidos.item(sel[0])['values'][4]

        top = ctk.CTkToplevel(self.parent.winfo_toplevel())
        top.title(f"Alterar Estado - Pedido #{id_ped}")
        top.geometry("350x200")
        top.transient(self.parent.winfo_toplevel())
        top.grab_set()

        ctk.CTkLabel(top, text="Novo Estado do Pedido:", font=("Arial", 12, "bold")).pack(pady=(20, 10))
        
        cmb_estado = ctk.CTkComboBox(top, values=["Pendente", "Em Andamento", "Concluído", "Entregue"], width=200, state="readonly")
        cmb_estado.set(status_atual)
        cmb_estado.pack(pady=10)

        def guardar_estado():
            novo_estado = cmb_estado.get()
            pedidos = JSONManager.carregar(ARQUIVO_PEDIDOS)
            for p in pedidos:
                if p.get("id", p.get("id_pedido")) == id_ped:
                    p["estado"] = novo_estado
                    p["status"] = novo_estado
                    break
            JSONManager.salvar(pedidos, ARQUIVO_PEDIDOS)
            self.atualizar_tabela()
            top.destroy()

        ctk.CTkButton(top, text="GUARDAR", fg_color="#1f538d", command=guardar_estado).pack(pady=10)

    def soft_delete_pedido(self):
        sel = self.tree_pedidos.selection()
        if not sel: return
        id_ped = self.tree_pedidos.item(sel[0])['values'][0]

        if messagebox.askyesno("Confirmar Eliminação", f"Tem a certeza que deseja eliminar o Pedido #{id_ped}?\n(O registo será mantido na base de dados por segurança)."):
            pedidos = JSONManager.carregar(ARQUIVO_PEDIDOS)
            for p in pedidos:
                if p.get("id", p.get("id_pedido")) == id_ped:
                    p["ativo"] = False 
                    p["estado"] = "Cancelado" 
                    p["status"] = "Cancelado"
                    break
            JSONManager.salvar(pedidos, ARQUIVO_PEDIDOS)
            self.atualizar_tabela()