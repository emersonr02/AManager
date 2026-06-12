import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from services.pedido_service import PedidoService
from gui.dialogs.novo_pedido import JanelaNovoPedido
from gui.dialogs.editar_pedido import JanelaEditarPedido

class PedidosTab:
    def __init__(self, parent_frame, f_padrao, f_titulo):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.f_titulo = f_titulo
        
        # Fundo ligeiramente cinza para fazer os cartões brancos "saltarem"
        self.parent.configure(fg_color="#f0f2f5")
        
        self.construir_layout()
        self.atualizar_tabela()

    def construir_layout(self):
        # 1. HEADER (Título e Botão + Novo)
        frm_header = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(frm_header, text="Gestão de Pedidos", font=ctk.CTkFont(size=22, weight="bold"), text_color="#1f538d").pack(side="left")
        ctk.CTkButton(frm_header, text="+ Novo Pedido", fg_color="#28a745", text_color="white", font=self.f_padrao, command=self.abrir_novo_pedido).pack(side="right")

        # 2. CARDS DE KPI (Adicionados ícones focados em fluxo de pedidos)
        frm_kpi = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_kpi.pack(fill="x", padx=20, pady=10)
        
        self.lbl_kpi_total = self.criar_card_kpi(frm_kpi, "📋 Total de Pedidos", "0", 0)
        self.lbl_kpi_andamento = self.criar_card_kpi(frm_kpi, "⏳ Em Andamento", "0", 1)
        self.lbl_kpi_entregues = self.criar_card_kpi(frm_kpi, "✅ Entregues", "0", 2)

        # 3. ÁREA DA TABELA (Container Branco)
        frm_lista = ctk.CTkFrame(self.parent, fg_color="white", corner_radius=10)
        frm_lista.pack(fill="both", expand=True, padx=20, pady=10)

        # Pequena barra de pesquisa acima da tabela (Opcional, igual à imagem)
        frm_search = ctk.CTkFrame(frm_lista, fg_color="transparent")
        frm_search.pack(fill="x", padx=10, pady=10)
        ctk.CTkEntry(frm_search, placeholder_text="Pesquisar pedido...", width=250, fg_color="#f0f2f5", border_width=0).pack(side="left")

        cols = ("id", "data", "requerente", "projeto", "status", "tech")
        self.tree_pedidos = ttk.Treeview(frm_lista, columns=cols, show="headings", style="Custom.Treeview")
        for c in cols: 
            self.tree_pedidos.heading(c, text=c.upper())
            
        self.tree_pedidos.column("id", width=50, anchor="center")
        self.tree_pedidos.column("data", width=120, anchor="center")
        self.tree_pedidos.column("status", width=120, anchor="center")
        self.tree_pedidos.column("tech", width=80, anchor="center")

        self.tree_pedidos.bind("<Double-1>", self.abrir_edicao)

        sb_ped = ttk.Scrollbar(frm_lista, orient="vertical", command=self.tree_pedidos.yview)
        self.tree_pedidos.configure(yscrollcommand=sb_ped.set)
        sb_ped.pack(fill="y", side="right", pady=10)
        self.tree_pedidos.pack(fill="both", expand=True, side="left", padx=10, pady=10)

        self.configurar_estilo_tabela()

    def criar_card_kpi(self, parent, titulo, valor, col):
        # Cartão branco com cantos arredondados
        card = ctk.CTkFrame(parent, fg_color="white", corner_radius=10, height=100)
        card.pack(side="left", fill="x", expand=True, padx=5)
        card.pack_propagate(False) # Mantém a altura fixa
        
        ctk.CTkLabel(card, text=titulo, text_color="gray20", font=ctk.CTkFont(family="Arial", size=13, weight="bold")).pack(anchor="w", padx=15, pady=(15, 0))
        lbl_valor = ctk.CTkLabel(card, text=valor, text_color="#1f538d", font=ctk.CTkFont(size=32, weight="bold"))
        lbl_valor.pack(anchor="w", padx=15, pady=5)
        return lbl_valor

    def configurar_estilo_tabela(self):
        style = ttk.Style()
        # Estilização para combinar com fundo claro
        style.theme_use("default")
        style.configure("Custom.Treeview", background="white", foreground="black", rowheight=30, fieldbackground="white", borderwidth=0)
        style.configure("Custom.Treeview.Heading", background="#f0f2f5", foreground="gray30", font=("Arial", 11, "bold"), borderwidth=0)
        style.map("Custom.Treeview", background=[("selected", "#1f538d")], foreground=[("selected", "white")])

    def atualizar_tabela(self):
        for i in self.tree_pedidos.get_children(): self.tree_pedidos.delete(i)
        pedidos = PedidoService.obter_todos()
        
        andamento = 0
        entregues = 0
        
        for p in pedidos:
            status = p.get("status")
            if status == "Em Andamento": andamento += 1
            if status == "Entregue": entregues += 1
            
            self.tree_pedidos.insert("", "end", values=(
                p.get("id"), p.get("data_pedido"), p.get("requerente"), 
                p.get("projeto"), status, p.get("tecnologia")
            ))
            
        # Atualiza os números dos cartões KPI
        self.lbl_kpi_total.configure(text=str(len(pedidos)))
        self.lbl_kpi_andamento.configure(text=str(andamento))
        self.lbl_kpi_entregues.configure(text=str(entregues))

    def abrir_novo_pedido(self):
        JanelaNovoPedido(self.parent.winfo_toplevel(), self.atualizar_tabela, self.f_padrao, self.f_titulo)

    def abrir_edicao(self, event=None):
        sel = self.tree_pedidos.selection()
        if not sel: return
        id_ped = self.tree_pedidos.item(sel[0])['values'][0]
        
        for p in PedidoService.obter_todos():
            if p.get("id") == id_ped:
                # Necessário garantir que o fundo do pop-up de edição também seja configurado depois
                JanelaEditarPedido(self.parent.winfo_toplevel(), p, self.atualizar_tabela)
                break