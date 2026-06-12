import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from services.pedido_service import PedidoService
from database.json_manager import JSONManager
from config.paths import ARQUIVO_PROJETOS

class JanelaNovoPedido(ctk.CTkToplevel):
    def __init__(self, parent, callback_atualizar, f_padrao, f_titulo):
        super().__init__(parent)
        self.title("Criar Novo Pedido")
        self.geometry("450x550")
        self.transient(parent)
        self.grab_set()
        
        self.callback = callback_atualizar
        self.f_padrao = f_padrao
        
        # Fundo branco para combinar com o tema
        self.configure(fg_color="#fcfcfc")
        
        ctk.CTkLabel(self, text="Detalhes do Pedido", font=f_titulo).pack(pady=15)

        ctk.CTkLabel(self, text="Requerente (Nome/Email):", font=f_padrao).pack(anchor="w", padx=20)
        self.ent_ped_req = ctk.CTkEntry(self, font=f_padrao, fg_color="white")
        self.ent_ped_req.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(self, text="Projeto:", font=f_padrao).pack(anchor="w", padx=20)
        projetos = JSONManager.carregar(ARQUIVO_PROJETOS)
        self.cmb_ped_proj = ctk.CTkComboBox(self, values=projetos, font=f_padrao, fg_color="white", state="readonly")
        self.cmb_ped_proj.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(self, text="Tecnologia:", font=f_padrao).pack(anchor="w", padx=20)
        self.cmb_ped_tech = ctk.CTkComboBox(self, values=["FDM", "SLA", "SLS"], font=f_padrao, fg_color="white", state="readonly")
        self.cmb_ped_tech.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(self, text="Observação (Qtd / Prioridade):", font=f_padrao).pack(anchor="w", padx=20)
        self.ent_ped_obs = ctk.CTkTextbox(self, height=80, font=f_padrao, fg_color="white")
        self.ent_ped_obs.pack(fill="x", padx=20, pady=5)

        ctk.CTkButton(self, text="REGISTAR PEDIDO", fg_color="#1f538d", text_color="white", font=f_titulo, command=self.gravar).pack(fill="x", padx=20, pady=30)

    def gravar(self):
        req = self.ent_ped_req.get().strip()
        proj = self.cmb_ped_proj.get()
        
        if not req or not proj:
            messagebox.showwarning("Aviso", "Preencha o requerente e o projeto.")
            return

        PedidoService.criar_pedido(
            requerente=req, projeto=proj, tecnologia=self.cmb_ped_tech.get(),
            responsavel="Sistema", observacao=self.ent_ped_obs.get("1.0", tk.END).strip()
        )
        
        self.callback()
        self.destroy()