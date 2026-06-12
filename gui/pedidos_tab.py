import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from services.pedido_service import PedidoService
# from gui.dialogs.editar_pedido import JanelaEditarPedido # Descomentaremos ao criar o dialog

class PedidosTab:
    def __init__(self, parent_frame, f_padrao, f_titulo):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.f_titulo = f_titulo
        
        self.construir_layout()
        self.atualizar_tabela()

    def construir_layout(self):
        # Formulário Esquerdo
        frm_form = ctk.CTkFrame(self.parent, width=320)
        frm_form.pack(side="left", fill="y", padx=10, pady=10)

        ctk.CTkLabel(frm_form, text="Novo Pedido", font=self.f_titulo).pack(pady=15)

        ctk.CTkLabel(frm_form, text="Requerente (Nome/Email):", font=self.f_padrao).pack(anchor="w", padx=10)
        self.ent_ped_req = ctk.CTkEntry(frm_form, font=self.f_padrao)
        self.ent_ped_req.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(frm_form, text="Projeto:", font=self.f_padrao).pack(anchor="w", padx=10)
        self.cmb_ped_proj = ctk.CTkComboBox(frm_form, values=[], font=self.f_padrao, state="readonly") # Valores virão do service depois
        self.cmb_ped_proj.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(frm_form, text="Tecnologia:", font=self.f_padrao).pack(anchor="w", padx=10)
        self.cmb_ped_tech = ctk.CTkComboBox(frm_form, values=["FDM", "SLA", "SLS"], font=self.f_padrao, state="readonly")
        self.cmb_ped_tech.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(frm_form, text="Responsável (Interno):", font=self.f_padrao).pack(anchor="w", padx=10)
        self.cmb_ped_resp = ctk.CTkComboBox(frm_form, values=[], font=self.f_padrao) # Valores virão do service depois
        self.cmb_ped_resp.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(frm_form, text="Status Inicial: Em Andamento (Automático)", font=self.f_padrao, text_color="#94a3b8").pack(anchor="w", padx=10, pady=(10, 5))

        ctk.CTkLabel(frm_form, text="Observação (Qtd / Prioridade):", font=self.f_padrao).pack(anchor="w", padx=10)
        self.ent_ped_obs = ctk.CTkTextbox(frm_form, height=80, font=self.f_padrao)
        self.ent_ped_obs.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(frm_form, text="REGISTAR PEDIDO", fg_color="#1f538d", font=self.f_titulo, command=self.gravar).pack(fill="x", padx=10, pady=20)

        # Tabela Direita
        frm_lista = ctk.CTkFrame(self.parent)
        frm_lista.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        cols = ("id", "data", "requerente", "projeto", "status", "tech", "atualizacao")
        self.tree_pedidos = ttk.Treeview(frm_lista, columns=cols, show="headings")
        for c in cols: 
            self.tree_pedidos.heading(c, text=c.upper())
            
        self.tree_pedidos.column("id", width=30, anchor="center")
        self.tree_pedidos.column("data", width=80, anchor="center")
        self.tree_pedidos.column("status", width=80, anchor="center")
        self.tree_pedidos.column("tech", width=50, anchor="center")

        # self.tree_pedidos.bind("<Double-1>", self.abrir_edicao)

        sb_ped = ttk.Scrollbar(frm_lista, orient="vertical", command=self.tree_pedidos.yview)
        self.tree_pedidos.configure(yscrollcommand=sb_ped.set)
        sb_ped.pack(fill="y", side="right")
        self.tree_pedidos.pack(fill="both", expand=True, side="left")

    def atualizar_tabela(self):
        for i in self.tree_pedidos.get_children(): 
            self.tree_pedidos.delete(i)
            
        # Repare como a chamada ao banco sumiu e agora usamos o Service
        pedidos = PedidoService.obter_todos()
        
        for p in pedidos:
            self.tree_pedidos.insert("", "end", values=(
                p.get("id"), p.get("data_pedido"), p.get("requerente"), 
                p.get("projeto"), p.get("status"), p.get("tecnologia"), 
                p.get("data_atualizacao")
            ))

    def gravar(self):
        req = self.ent_ped_req.get().strip()
        proj = self.cmb_ped_proj.get()
        
        if not req or not proj:
            messagebox.showwarning("Aviso", "Preencha o requerente e o projeto.")
            return

        # A lógica pesada foi movida. A GUI só manda os dados.
        PedidoService.criar_pedido(
            requerente=req,
            projeto=proj,
            tecnologia=self.cmb_ped_tech.get(),
            responsavel=self.cmb_ped_resp.get(),
            observacao=self.ent_ped_obs.get("1.0", tk.END).strip()
        )
        
        self.ent_ped_req.delete(0, tk.END)
        self.ent_ped_obs.delete("1.0", tk.END)
        self.atualizar_tabela()
        messagebox.showinfo("Sucesso", "Pedido registado no backlog.")

    # def abrir_edicao(self, event=None):
    #     # Método comentado temporariamente até criarmos o dialog de edição
    #     pass