import os
import customtkinter as ctk
from tkinter import ttk
from config.paths import BASE_DIR

from gui.pedidos_tab import PedidosTab
from gui.producao_tab import ProducaoTab
from gui.historico_tab import HistoricoTab
from gui.parque_tab import ParqueTab

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AppIndustrialI3D(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gestão de Produção i3D | CEiiA")
        self.geometry("1300x800")
        
        icon_path = os.path.join(BASE_DIR, "logo_ceiia.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        # Objetos de Fonte Dinâmica
        self.f_padrao = ctk.CTkFont(family="Arial", size=13)
        self.f_titulo = ctk.CTkFont(family="Arial", size=18, weight="bold")
        self.bind("<Configure>", self.redimensionar_fontes)

        # Sistema de Abas principal
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_pedidos = self.tabs.add("Administração de Pedidos")
        self.tab_reg = self.tabs.add("Lançar Ordem de Produção")
        self.tab_hist = self.tabs.add("Monitor & Exportação (Histórico)")
        self.tab_parque = self.tabs.add("Gestão do Parque de Impressoras")

        # Inicializa as instâncias das UIs (garantindo retenção de memória)
        self.pedidos_ui = PedidosTab(self.tab_pedidos, self.f_padrao, self.f_titulo)
        self.producao_ui = ProducaoTab(self.tab_reg, self.f_padrao, self.f_titulo, self)
        self.historico_ui = HistoricoTab(self.tab_hist, self.f_padrao, self.f_titulo, self)
        self.parque_ui = ParqueTab(self.tab_parque, self.f_padrao, self.f_titulo)

    def redimensionar_fontes(self, event):
        if event.widget == self:
            w = self.winfo_width()
            base = max(11, int(w / 110))
            self.f_padrao.configure(size=base)
            self.f_titulo.configure(size=int(base * 1.3))
            
            style = ttk.Style()
            style.configure("Treeview", font=("Arial", base), rowheight=int(base * 2.2))
            style.configure("Treeview.Heading", font=("Arial", int(base * 1.1), "bold"))