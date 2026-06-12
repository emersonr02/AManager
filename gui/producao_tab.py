import os
from datetime import datetime
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog

from config.paths import ARQUIVO_PROJETOS, ARQUIVO_MATERIAIS, ARQUIVO_LOGS
from database.json_manager import JSONManager
from services.producao_service import ProducaoService
from services.maquina_service import MaquinaService
from gui.dialogs.gestao_simples import JanelaGestaoSimples

class ProducaoTab:
    def __init__(self, parent_frame, f_padrao, f_titulo, master_app):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.f_titulo = f_titulo
        self.master_app = master_app 
        
        self.construir_layout()
        self.atualizar_combos()

    def mascara_tempo(self, event, widget):
        """Método local para auxiliar o input do utilizador."""
        if event.keysym in ["BackSpace", "Delete", "Left", "Right", "Tab"]: return
        texto = widget.get().replace(":", "")
        texto = "".join([c for c in texto if c.isdigit()])
        if len(texto) >= 2:
            widget.delete(0, tk.END)
            widget.insert(0, f"{texto[:2]}:{texto[2:4]}")
        if len(widget.get()) > 5:
            widget.delete(5, tk.END)

    def construir_layout(self):
        frm = ctk.CTkFrame(self.parent)
        frm.pack(fill="both", expand=True, padx=15, pady=15)
        frm.columnconfigure(1, weight=1)

        ctk.CTkLabel(frm, text="Tecnologia AM:", font=self.f_padrao).grid(row=0, column=0, padx=15, pady=10, sticky="e")
        self.cmb_tech = ctk.CTkComboBox(frm, values=["FDM", "SLA", "SLS"], font=self.f_padrao, state="readonly", command=self.mudar_tecnologia)
        self.cmb_tech.grid(row=0, column=1, padx=15, pady=10, sticky="w")

        ctk.CTkLabel(frm, text="Máquina Destino:", font=self.f_padrao).grid(row=1, column=0, padx=15, pady=10, sticky="e")
        self.cmb_maq = ctk.CTkComboBox(frm, values=[], width=250, font=self.f_padrao, state="readonly")
        self.cmb_maq.grid(row=1, column=1, padx=15, pady=10, sticky="w")

        ctk.CTkLabel(frm, text="Pasta do Projeto (Rede/Local):", font=self.f_padrao).grid(row=2, column=0, padx=15, pady=10, sticky="e")
        self.ent_pasta = ctk.CTkEntry(frm, placeholder_text="\\\\ceiia.com\\PPS\\...", font=self.f_padrao)
        self.ent_pasta.grid(row=2, column=1, padx=15, pady=10, sticky="ew")
        ctk.CTkButton(frm, text="Mapear Diretório", width=100, font=self.f_padrao, command=self.mapear_diretorio).grid(row=2, column=2, padx=15, pady=10)

        ctk.CTkLabel(frm, text="ID - Projeto:", font=self.f_padrao).grid(row=3, column=0, padx=15, pady=10, sticky="e")
        frm_proj = ctk.CTkFrame(frm, fg_color="transparent")
        frm_proj.grid(row=3, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
        self.cmb_proj = ctk.CTkComboBox(frm_proj, values=[], font=self.f_padrao, state="readonly")
        self.cmb_proj.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(frm_proj, text="⚙️ Gerir", width=70, font=self.f_padrao, command=lambda: JanelaGestaoSimples(self.master_app, "Gestão de Projetos", "ID (6 dígitos)", "Nome do Projeto", ARQUIVO_PROJETOS, self.atualizar_combos)).pack(side="right")

        ctk.CTkLabel(frm, text="Material e Fabricante:", font=self.f_padrao).grid(row=4, column=0, padx=15, pady=10, sticky="e")
        frm_mat = ctk.CTkFrame(frm, fg_color="transparent")
        frm_mat.grid(row=4, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
        self.cmb_mat = ctk.CTkComboBox(frm_mat, values=[], font=self.f_padrao, state="readonly")
        self.cmb_mat.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(frm_mat, text="⚙️ Gerir", width=70, font=self.f_padrao, command=lambda: JanelaGestaoSimples(self.master_app, "Gestão de Materiais", "Nome do Material", "Fabricante", ARQUIVO_MATERIAIS, self.atualizar_combos)).pack(side="right")

        ctk.CTkLabel(frm, text="Tempo Máquina (HH:MM):", font=self.f_padrao).grid(row=5, column=0, padx=15, pady=10, sticky="e")
        self.ent_tempo = ctk.CTkEntry(frm, placeholder_text="02:30", font=self.f_padrao)
        self.ent_tempo.grid(row=5, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
        self.ent_tempo.bind("<KeyRelease>", lambda e: self.mascara_tempo(e, self.ent_tempo))

        # Campos Dinâmicos (FDM/SLA vs SLS)
        self.lbl_quant = ctk.CTkLabel(frm, text="Quantidade (g/ml):", font=self.f_padrao)
        self.ent_quant = ctk.CTkEntry(frm, placeholder_text="150.5", font=self.f_padrao)
        
        self.lbl_altura = ctk.CTkLabel(frm, text="Altura da Cuba (mm):", font=self.f_padrao)
        self.ent_altura = ctk.CTkEntry(frm, placeholder_text="470", font=self.f_padrao)
        self.lbl_perc = ctk.CTkLabel(frm, text="% de Pó Novo:", font=self.f_padrao)
        self.ent_perc = ctk.CTkEntry(frm, placeholder_text="0.3", font=self.f_padrao)

        self.lbl_resp = ctk.CTkLabel(frm, text="Operador (Iniciais):", font=self.f_padrao)
        self.cmb_resp = ctk.CTkComboBox(frm, values=[], font=self.f_padrao)

        self.btn_salvar = ctk.CTkButton(frm, text="INICIAR FABRICO", fg_color="#1f538d", height=45, font=self.f_titulo, command=self.gravar_producao)
        
        self.mudar_tecnologia("FDM")

    def atualizar_combos(self, *args):
        tech = self.cmb_tech.get()
        
        # O MaquinaService filtra as inativas para nós
        maquinas_ativas = MaquinaService.obter_ativas_por_tecnologia(tech)
        self.cmb_maq.configure(values=maquinas_ativas)
        self.cmb_maq.set(maquinas_ativas[0] if maquinas_ativas else "Nenhuma Ativa")
        
        self.cmb_proj.configure(values=JSONManager.carregar(ARQUIVO_PROJETOS))
        self.cmb_mat.configure(values=JSONManager.carregar(ARQUIVO_MATERIAIS))
        
        logs = JSONManager.carregar(ARQUIVO_LOGS)
        operadores = list(set([l.get("responsavel", "").strip() for l in logs if l.get("responsavel", "").strip()]))
        self.cmb_resp.configure(values=operadores)
        if not self.cmb_resp.get() and operadores:
            self.cmb_resp.set(operadores[-1])

    def mudar_tecnologia(self, tech):
        self.atualizar_combos()
        if tech == "SLS":
            self.lbl_quant.grid_remove(); self.ent_quant.grid_remove()
            self.lbl_altura.grid(row=6, column=0, padx=15, pady=5, sticky="e")
            self.ent_altura.grid(row=6, column=1, columnspan=2, padx=15, pady=5, sticky="ew")
            self.lbl_perc.grid(row=7, column=0, padx=15, pady=5, sticky="e")
            self.ent_perc.grid(row=7, column=1, columnspan=2, padx=15, pady=5, sticky="ew")
            self.lbl_resp.grid(row=8, column=0, padx=15, pady=10, sticky="e")
            self.cmb_resp.grid(row=8, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
            self.btn_salvar.grid(row=9, column=0, columnspan=3, pady=20, padx=15, sticky="ew")
        else:
            self.lbl_altura.grid_remove(); self.ent_altura.grid_remove()
            self.lbl_perc.grid_remove(); self.ent_perc.grid_remove()
            self.lbl_quant.grid(row=6, column=0, padx=15, pady=10, sticky="e")
            self.ent_quant.grid(row=6, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
            self.lbl_resp.grid(row=7, column=0, padx=15, pady=10, sticky="e")
            self.cmb_resp.grid(row=7, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
            self.btn_salvar.grid(row=8, column=0, columnspan=3, pady=20, padx=15, sticky="ew")

    def mapear_diretorio(self):
        pasta = filedialog.askdirectory()
        if pasta:
            self.ent_pasta.delete(0, tk.END)
            self.ent_pasta.insert(0, os.path.normpath(pasta))

    def gravar_producao(self):
        tech = self.cmb_tech.get()
        t_maq = self.ent_tempo.get().strip()

        if not ProducaoService.validar_formato_tempo(t_maq):
            messagebox.showerror("Erro de Formato", "O tempo deve estar no formato exato HH:MM.")
            return

        altura_c = 0.0
        perc_p = 0.0
        
        # Delegação do cálculo complexo para o serviço
        if tech == "SLS":
            try:
                altura_c = float(self.ent_altura.get().strip().replace(',', '.'))
                perc_p = float(self.ent_perc.get().strip().replace(',', '.'))
                q_maq = ProducaoService.calcular_consumo_sls(altura_c, perc_p)
            except ValueError:
                messagebox.showerror("Erro", "Altura e % de Pó Novo devem ser números válidos.")
                return
        else:
            try: q_maq = float(self.ent_quant.get().strip().replace(',', '.'))
            except ValueError: 
                messagebox.showerror("Erro", "Quantidade inválida.")
                return

        if not self.cmb_proj.get() or not self.cmb_resp.get() or not self.ent_pasta.get() or "Nenhuma" in self.cmb_maq.get():
            messagebox.showerror("Aviso", "Preenche todos os campos antes de iniciar o fabrico.")
            return

        logs = JSONManager.carregar(ARQUIVO_LOGS)
        novo_id = max([l.get("id", 0) for l in logs]) + 1 if logs else 1
        
        novo_log = {
            "id": novo_id, "localizacao": self.ent_pasta.get().strip(), 
            "id_maquina": self.cmb_maq.get(), "nr_projeto": self.cmb_proj.get(),
            "data_inicio": datetime.now().strftime("%Y-%m-%d"),
            "hora_maquina": t_maq, "material": self.cmb_mat.get(), 
            "quantidade": round(q_maq, 4), "altura": altura_c, "perc_po": perc_p,
            "tecnologia": tech, "responsavel": self.cmb_resp.get().strip(),
            "estado": "Em Andamento", "erro": ""
        }
        
        logs.append(novo_log)
        JSONManager.salvar(logs, ARQUIVO_LOGS)
        
        messagebox.showinfo("Sucesso", "Produção salva na base de dados JSON!")
        
        # Limpar campos visuais
        self.ent_tempo.delete(0, tk.END)
        if tech == "SLS":
            self.ent_altura.delete(0, tk.END); self.ent_perc.delete(0, tk.END)
        else:
            self.ent_quant.delete(0, tk.END)
        
        self.atualizar_combos()