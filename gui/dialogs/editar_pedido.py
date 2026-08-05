import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from config.paths import ARQUIVO_PEDIDOS, ARQUIVO_PROJETOS, ARQUIVO_MATERIAIS
from database.json_manager import JSONManager
from services.pedido_service import PedidoService

class JanelaEditarPedido(ctk.CTkToplevel):
    def __init__(self, parent, pedido, callback_atualizar):
        super().__init__(parent)
        self.pedido = pedido
        self.callback_atualizar = callback_atualizar
        
        self.title(f"Editar Pedido #{self.pedido.get('id')}")
        self.geometry("820x820")
        self.configure(fg_color="#fcfcfc")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()

        self.linhas_pecas = [] 
        self.carregar_dados_auxiliares()
        self.construir_layout()
        self.preencher_dados_existentes()

    def carregar_dados_auxiliares(self):
        """ Carrega os dados dos ficheiros JSON aceitando Strings ou Dicionários """
        # 1. Projetos
        projs = JSONManager.carregar(ARQUIVO_PROJETOS)
        self.lista_projetos_fmt = []
        for p in projs:
            if isinstance(p, dict):
                id_p = p.get("id", p.get("nr_projeto", p.get("numero", "")))
                nome_p = p.get("nome", p.get("nome_projeto", ""))
                self.lista_projetos_fmt.append(f"{id_p} - {nome_p}" if nome_p else str(id_p))
            elif isinstance(p, str):
                self.lista_projetos_fmt.append(p)

        if not self.lista_projetos_fmt:
            self.lista_projetos_fmt = ["Sem projetos registados"]

        # 2. Materiais
        mats = JSONManager.carregar(ARQUIVO_MATERIAIS)
        self.lista_materiais_fmt = []
        for m in mats:
            if isinstance(m, dict):
                nome_m = m.get("nome", m.get("material", m.get("nome_material", "")))
                fab = m.get("fabricante", "")
                self.lista_materiais_fmt.append(f"{nome_m} ({fab})" if fab else str(nome_m))
            elif isinstance(m, str):
                self.lista_materiais_fmt.append(m)

        if not self.lista_materiais_fmt:
            self.lista_materiais_fmt = ["N/A"]

    def construir_layout(self):
        ctk.CTkLabel(self, text=f"Editar Pedido #{self.pedido.get('id')}", font=("Arial", 18, "bold"), text_color="#1f538d").pack(pady=(15, 5))

        # --- CABEÇALHO DO PEDIDO ---
        frm_master = ctk.CTkFrame(self, fg_color="white", border_width=1, border_color="#e0e0e0", corner_radius=8)
        frm_master.pack(fill="x", padx=20, pady=10)

        # Linha 1
        ctk.CTkLabel(frm_master, text="Requerente (Email):", font=("Arial", 11, "bold"), text_color="gray40").grid(row=0, column=0, padx=10, pady=(15, 5), sticky="w")
        self.ent_req = ctk.CTkEntry(frm_master, width=220, fg_color="#f0f2f5", text_color="black")
        self.ent_req.grid(row=0, column=1, padx=10, pady=(15, 5), sticky="w")

        ctk.CTkLabel(frm_master, text="Data de Entrega:", font=("Arial", 11, "bold"), text_color="gray40").grid(row=0, column=2, padx=10, pady=(15, 5), sticky="w")
        self.ent_data = ctk.CTkEntry(frm_master, width=150, fg_color="#f0f2f5", text_color="black")
        self.ent_data.grid(row=0, column=3, padx=10, pady=(15, 5), sticky="w")

        # Linha 2
        ctk.CTkLabel(frm_master, text="Projeto (ID - Nome):", font=("Arial", 11, "bold"), text_color="gray40").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.cmb_proj = ctk.CTkComboBox(frm_master, values=self.lista_projetos_fmt, width=220, fg_color="#f0f2f5", text_color="black", state="readonly")
        self.cmb_proj.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        ctk.CTkLabel(frm_master, text="Tecnologia Base:", font=("Arial", 11, "bold"), text_color="gray40").grid(row=1, column=2, padx=10, pady=5, sticky="w")
        self.cmb_tech = ctk.CTkComboBox(frm_master, values=["FDM", "SLA", "SLS"], width=150, fg_color="#f0f2f5", text_color="black", state="readonly")
        self.cmb_tech.grid(row=1, column=3, padx=10, pady=5, sticky="w")

        # Linha 3
        ctk.CTkLabel(frm_master, text="Link / Pasta (Rede):", font=("Arial", 11, "bold"), text_color="gray40").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.ent_link = ctk.CTkEntry(frm_master, width=490, fg_color="#f0f2f5", text_color="black")
        self.ent_link.grid(row=2, column=1, columnspan=3, padx=10, pady=5, sticky="w")

        # Linha 4
        ctk.CTkLabel(frm_master, text="Observações:", font=("Arial", 11, "bold"), text_color="gray40").grid(row=3, column=0, padx=10, pady=(5, 15), sticky="nw")
        self.txt_obs = ctk.CTkTextbox(frm_master, width=490, height=50, fg_color="#f0f2f5", text_color="black")
        self.txt_obs.grid(row=3, column=1, columnspan=3, padx=10, pady=(5, 15), sticky="w")

        # --- GRELHA DINÂMICA DE PEÇAS ---
        frm_titulo_pecas = ctk.CTkFrame(self, fg_color="transparent")
        frm_titulo_pecas.pack(fill="x", padx=20, pady=(10, 0))
        
        ctk.CTkLabel(frm_titulo_pecas, text="Lista de Peças a Fabricar:", font=("Arial", 13, "bold"), text_color="#1f538d").pack(side="left")
        ctk.CTkButton(frm_titulo_pecas, text="+ Adicionar Peça", fg_color="#28a745", hover_color="#218838", width=120, height=28, command=self.adicionar_linha_peca).pack(side="right")

        self.frm_scroll_pecas = ctk.CTkScrollableFrame(self, fg_color="#f8f9fa", border_width=1, border_color="#e0e0e0", corner_radius=8, height=220)
        self.frm_scroll_pecas.pack(fill="x", padx=20, pady=5)

        # --- BOTÃO GUARDAR ---
        self.btn_salvar = ctk.CTkButton(self, text="GUARDAR ALTERAÇÕES", fg_color="#1f538d", hover_color="#143a63", text_color="white", font=("Arial", 13, "bold"), command=self.salvar_alteracoes, height=45)
        self.btn_salvar.pack(fill="x", padx=20, pady=20)

    def preencher_dados_existentes(self):
        self.ent_req.insert(0, self.pedido.get("requerente_email", self.pedido.get("requerente", "")))
        self.ent_data.insert(0, self.pedido.get("data_entrega", ""))
        self.ent_link.insert(0, self.pedido.get("link_arquivos", ""))
        
        if self.pedido.get("observacoes"):
            self.txt_obs.insert("1.0", self.pedido.get("observacoes"))
            
        self.cmb_tech.set(self.pedido.get("tecnologia", "FDM"))

        # Preenche o Projeto
        nr_p = self.pedido.get("nr_projeto", self.pedido.get("projeto", ""))
        nome_p = self.pedido.get("nome_projeto", "")
        fmt = f"{nr_p} - {nome_p}" if nome_p else str(nr_p)
        if fmt in self.lista_projetos_fmt:
            self.cmb_proj.set(fmt)
        elif self.lista_projetos_fmt:
            self.cmb_proj.set(self.lista_projetos_fmt[0])

        # Preenche as peças existentes
        pecas = self.pedido.get("pecas", [])
        if pecas:
            for p in pecas:
                self.adicionar_linha_peca(pn=p.get("pn", ""), mat=p.get("material", ""), qtd=p.get("qtd_solicitada", 1))
        else:
            self.adicionar_linha_peca()

    def adicionar_linha_peca(self, pn="", mat="", qtd=""):
        linha_frm = ctk.CTkFrame(self.frm_scroll_pecas, fg_color="transparent")
        linha_frm.pack(fill="x", pady=3)

        ent_pn = ctk.CTkEntry(linha_frm, placeholder_text="Part Number", width=300, fg_color="white", text_color="black")
        ent_pn.insert(0, pn)
        ent_pn.pack(side="left", padx=(5, 10))

        cmb_mat = ctk.CTkComboBox(linha_frm, values=self.lista_materiais_fmt, width=220, fg_color="white", text_color="black", state="readonly")
        if mat in self.lista_materiais_fmt:
            cmb_mat.set(mat)
        cmb_mat.pack(side="left", padx=(0, 10))

        ent_qtd = ctk.CTkEntry(linha_frm, placeholder_text="Qtd", width=70, fg_color="white", text_color="black")
        ent_qtd.insert(0, str(qtd))
        ent_qtd.pack(side="left", padx=(0, 10))

        btn_remover = ctk.CTkButton(linha_frm, text="X", width=30, fg_color="#dc3545", hover_color="#c82333", command=lambda f=linha_frm: self.remover_linha(f))
        btn_remover.pack(side="left")

        self.linhas_pecas.append({"frame": linha_frm, "pn": ent_pn, "mat": cmb_mat, "qtd": ent_qtd})

    def remover_linha(self, frame_alvo):
        frame_alvo.destroy()
        self.linhas_pecas = [linha for linha in self.linhas_pecas if linha["frame"] != frame_alvo]

    def salvar_alteracoes(self):
        req = self.ent_req.get().strip()
        proj_sel = self.cmb_proj.get()
        data_ent = self.ent_data.get().strip()
        link = self.ent_link.get().strip()
        tech = self.cmb_tech.get()
        obs = self.txt_obs.get("1.0", tk.END).strip()

        if not req or not data_ent or proj_sel == "Sem projetos registados":
            messagebox.showerror("Erro", "Requerente, Projeto e Data de Entrega são obrigatórios.")
            return

        if len(self.linhas_pecas) == 0:
            messagebox.showerror("Erro", "O pedido deve conter pelo menos uma peça.")
            return

        if " - " in proj_sel:
            partes = proj_sel.split(" - ", 1)
            nr_proj, nome_proj = partes[0], partes[1]
        else:
            nr_proj, nome_proj = proj_sel, ""

        lista_pecas = []
        for linha in self.linhas_pecas:
            pn = linha["pn"].get().strip()
            mat_peca = linha["mat"].get()
            qtd_str = linha["qtd"].get().strip()
            
            if not pn or not qtd_str:
                messagebox.showerror("Erro", "Todas as peças listadas devem ter PN e Quantidade preenchidos.")
                return
            
            if not qtd_str.isdigit() or int(qtd_str) <= 0:
                messagebox.showerror("Erro", f"A quantidade da peça '{pn}' tem de ser um número inteiro válido.")
                return
                
            lista_pecas.append({
                "pn": pn,
                "material": mat_peca,
                "qtd_solicitada": int(qtd_str),
                "qtd_produzida": 0
            })

        pedido_atualizado = dict(self.pedido)
        pedido_atualizado.update({
            "requerente_email": req,
            "nr_projeto": nr_proj,
            "nome_projeto": nome_proj,
            "tecnologia": tech,
            "observacoes": obs,
            "data_entrega": data_ent,
            "link_arquivos": link,
            "pecas": lista_pecas,
        })
        PedidoService.atualizar_pedido(pedido_atualizado)

        messagebox.showinfo("Sucesso", "Pedido atualizado com sucesso!")
        self.callback_atualizar()
        self.destroy()