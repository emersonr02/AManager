import customtkinter as ctk
import tkinter as tk
from services.pedido_service import PedidoService

class JanelaEditarPedido(ctk.CTkToplevel):
    def __init__(self, parent, pedido, callback_atualizar):
        super().__init__(parent)
        self.title(f"Atualizar Pedido - #{pedido.get('id')}")
        self.geometry("450x400")
        self.transient(parent)
        self.grab_set()
        
        self.pedido = pedido
        self.callback = callback_atualizar
        
        ctk.CTkLabel(self, text=f"Requerente: {pedido.get('requerente')}", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        
        ctk.CTkLabel(self, text="Status do Pedido:").pack(pady=5)
        self.cmb_status = ctk.CTkComboBox(self, values=["Em Andamento", "Standby", "Impresso", "Entregue", "Cancelado"])
        self.cmb_status.pack(pady=5)
        self.cmb_status.set(pedido.get("status", "Em Andamento"))
        
        ctk.CTkLabel(self, text="Observação (Qtd / Prioridade):").pack(pady=5)
        self.txt_obs = ctk.CTkTextbox(self, height=100)
        self.txt_obs.pack(padx=20, pady=5, fill="x")
        self.txt_obs.insert("1.0", pedido.get("observacao", ""))
        
        ctk.CTkButton(self, text="SALVAR ATUALIZAÇÃO", fg_color="#1f538d", command=self.salvar).pack(pady=20, padx=20, fill="x")
        
    def salvar(self):
        self.pedido["status"] = self.cmb_status.get()
        self.pedido["observacao"] = self.txt_obs.get("1.0", tk.END).strip()
        
        PedidoService.atualizar_pedido(self.pedido)
        self.callback()
        self.destroy()