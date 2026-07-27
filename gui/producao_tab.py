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
        
        self.parent.configure(fg_color="#f0f2f5") # Garante o fundo claro consistente
        self.construir_layout()
        self.atualizar_combos()

    def mascara_tempo(self, event, widget):
        if event.keysym in ["BackSpace", "Delete", "Left", "Right", "Tab"]: return
        texto = widget.get().replace(":", "")
        texto = "".join([c for c in texto if c.isdigit()])
        if len(texto) >= 2:
            widget.delete(0, tk.END)
            widget.insert(0, f"{texto[:2]}:{texto[2:4]}")
        if len(widget.get()) > 5:
            widget.delete(5, tk.END)

    def construir_layout(self):
        # Frame Principal com design de cartão branco
        frm = ctk.CTkFrame(self.parent, fg_color="white", corner_radius=12, border_width=1, border_color="#e0e0e0")
        frm.pack(fill="both", expand=True, padx=20, pady=20)
        frm.columnconfigure(1, weight=1)

        # 1. Tecnologia AM
        ctk.CTkLabel(frm, text="Tecnologia AM:", font=self.f_padrao, text_color="gray30").grid(row=0, column=0, padx=15, pady=10, sticky="e")
        self.cmb_tech = ctk.CTkComboBox(frm, values=["FDM", "SLA", "SLS"], font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black", button_color="#1f538d", state="readonly", command=self.mudar_tecnologia)
        self.cmb_tech.grid(row=0, column=1, padx=15, pady=10, sticky="w")

        # 2. Máquina Destino
        ctk.CTkLabel(frm, text="Máquina Destino:", font=self.f_padrao, text_color="gray30").grid(row=1, column=0, padx=15, pady=10, sticky="e")
        self.cmb_maq = ctk.CTkComboBox(frm, values=[], width=250, font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black", button_color="#1f538d", state="readonly")
        self.cmb_maq.grid(row=1, column=1, padx=15, pady=10, sticky="w")

        # 3. Pasta do Projeto
        ctk.CTkLabel(frm, text="Pasta do Projeto (Rede/Local):", font=self.f_padrao, text_color="gray30").grid(row=2, column=0, padx=15, pady=10, sticky="e")
        self.ent_pasta = ctk.CTkEntry(frm, placeholder_text="\\\\ceiia.com\\PPS\\...", font=self.f_padrao, fg_color="#f0f2f5", border_color="gray80", text_color="black")
        self.ent_pasta.grid(row=2, column=1, padx=15, pady=10, sticky="ew")
        ctk.CTkButton(frm, text="Mapear", width=100, fg_color="#f0f2f5", text_color="black", hover_color="#e0e0e0", font=self.f_padrao, command=self.mapear_diretorio).grid(row=2, column=2, padx=15, pady=10)

        # 4. ID - Projeto
        ctk.CTkLabel(frm, text="ID - Projeto:", font=self.f_padrao, text_color="gray30").grid(row=3, column=0, padx=15, pady=10, sticky="e")
        frm_proj = ctk.CTkFrame(frm, fg_color="transparent")
        frm_proj.grid(row=3, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
        self.cmb_proj = ctk.CTkComboBox(frm_proj, values=[], font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black", button_color="#1f538d", state="readonly")
        self.cmb_proj.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(frm_proj, text="⚙️ Gerir", width=70, fg_color="#f0f2f5", text_color="black", hover_color="#e0e0e0", font=self.f_padrao, command=lambda: JanelaGestaoSimples(self.master_app, "Gestão de Projetos", "ID (6 dígitos)", "Nome do Projeto", ARQUIVO_PROJETOS, self.atualizar_combos)).pack(side="right")

        # 5. Material e Fabricante
        ctk.CTkLabel(frm, text="Material e Fabricante:", font=self.f_padrao, text_color="gray30").grid(row=4, column=0, padx=15, pady=10, sticky="e")
        frm_mat = ctk.CTkFrame(frm, fg_color="transparent")
        frm_mat.grid(row=4, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
        self.cmb_mat = ctk.CTkComboBox(frm_mat, values=[], font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black", button_color="#1f538d", state="readonly")
        self.cmb_mat.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(frm_mat, text="⚙️ Gerir", width=70, fg_color="#f0f2f5", text_color="black", hover_color="#e0e0e0", font=self.f_padrao, command=lambda: JanelaGestaoSimples(self.master_app, "Gestão de Materiais", "Nome do Material", "Fabricante", ARQUIVO_MATERIAIS, self.atualizar_combos)).pack(side="right")

        # 6. Tempo Máquina
        ctk.CTkLabel(frm, text="Tempo Máquina (HH:MM):", font=self.f_padrao, text_color="gray30").grid(row=5, column=0, padx=15, pady=10, sticky="e")
        self.ent_tempo = ctk.CTkEntry(frm, placeholder_text="02:30", font=self.f_padrao, fg_color="#f0f2f5", border_color="gray80", text_color="black")
        self.ent_tempo.grid(row=5, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
        self.ent_tempo.bind("<KeyRelease>", lambda e: self.mascara_tempo(e, self.ent_tempo))

        # 7. Campos Dinâmicos Genéricos
        self.lbl_quant = ctk.CTkLabel(frm, text="Quantidade (g/ml):", font=self.f_padrao, text_color="gray30")
        self.ent_quant = ctk.CTkEntry(frm, placeholder_text="150.5", font=self.f_padrao, fg_color="#f0f2f5", border_color="gray80", text_color="black")
        
        self.lbl_altura = ctk.CTkLabel(frm, text="Altura da Cuba (mm):", font=self.f_padrao, text_color="gray30")
        self.ent_altura = ctk.CTkEntry(frm, placeholder_text="470", font=self.f_padrao, fg_color="#f0f2f5", border_color="gray80", text_color="black")
        self.lbl_perc = ctk.CTkLabel(frm, text="% de Pó Novo:", font=self.f_padrao, text_color="gray30")
        self.ent_perc = ctk.CTkEntry(frm, placeholder_text="0.3", font=self.f_padrao, fg_color="#f0f2f5", border_color="gray80", text_color="black")

        # ----------------------------------------------------
        # --- NOVO BLOCO EXCLUSIVO SLS (CHECKLIST DE SEGURANÇA) ---
        # ----------------------------------------------------
        self.frm_sls_checklist = ctk.CTkFrame(frm, fg_color="#f8f9fa", corner_radius=10, border_width=1, border_color="#e0e0e0")
        
        ctk.CTkLabel(self.frm_sls_checklist, text="⚙️ Parâmetros Básicos e Checklist Crítico SLS", font=("Arial", 12, "bold"), text_color="#1f538d").grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(10, 5))

        # Campo: Lote do Pó (Preenchido automaticamente)
        ctk.CTkLabel(self.frm_sls_checklist, text="Lote do Pó:", font=self.f_padrao, text_color="gray30").grid(row=1, column=0, padx=15, pady=5, sticky="w")
        self.ent_lote = ctk.CTkEntry(self.frm_sls_checklist, width=150, fg_color="white", border_color="gray80", text_color="black")
        self.ent_lote.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # Campo: Fator de Escala
        ctk.CTkLabel(self.frm_sls_checklist, text="Factor de escala:", font=self.f_padrao, text_color="gray30").grid(row=1, column=2, padx=15, pady=5, sticky="w")
        self.ent_escala = ctk.CTkEntry(self.frm_sls_checklist, width=100, fg_color="white", border_color="gray80", text_color="black")
        self.ent_escala.grid(row=1, column=3, padx=5, pady=5, sticky="w")
        self.ent_escala.insert(0, "1.000")

        # Variáveis booleanas dos 9 Checks da tua imagem (Todas nascem como True)
        self.sls_vars = {
            "slicefix": tk.BooleanVar(value=True),
            "po_suficiente": tk.BooleanVar(value=True),
            "abastecimento": tk.BooleanVar(value=True),
            "home_pistao": tk.BooleanVar(value=True),
            "home_rolo": tk.BooleanVar(value=True),
            "z_adicional": tk.BooleanVar(value=True),
            "chiller": tk.BooleanVar(value=True),
            "ac": tk.BooleanVar(value=True),
            "pre_aquecimento": tk.BooleanVar(value=True),
        }

        # Grid de Checkboxes organizada horizontalmente em 3 colunas
        checks_config = [
            ("SliceFix OK", "slicefix", 2, 0),
            ("Quant. de pó suficiente", "po_suficiente", 2, 1),
            ("Abastecim/ de pó ligado", "abastecimento", 2, 2),
            ("Homing do Pistão", "home_pistao", 3, 0),
            ("Homing da Rolo", "home_rolo", 3, 1),
            ("Z adicional no topo", "z_adicional", 3, 2),
            ("Chiller ligado", "chiller", 4, 0),
            ("AC ligado", "ac", 4, 1),
            ("Pre-aquecimento", "pre_aquecimento", 4, 2),
        ]

        for text, key, row, col in checks_config:
            chk = ctk.CTkCheckBox(self.frm_sls_checklist, text=text, font=("Arial", 11), variable=self.sls_vars[key], command=self.validar_restricoes_botao)
            chk.grid(row=row, column=col, padx=15, pady=6, sticky="w")
        # ----------------------------------------------------

        # Operador e Botão Salvar
        self.lbl_resp = ctk.CTkLabel(frm, text="Operador (Iniciais):", font=self.f_padrao, text_color="gray30")
        self.cmb_resp = ctk.CTkComboBox(frm, values=[], font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black", button_color="#1f538d")

        self.btn_salvar = ctk.CTkButton(frm, text="🚀 INICIAR FABRICO", fg_color="#28a745", hover_color="#218838", height=45, font=self.f_titulo, command=self.gravar_producao)
        
        self.mudar_tecnologia("FDM")

    def atualizar_combos(self, *args):
        tech = self.cmb_tech.get()
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
        
        # Oculta todos antes de redesenhar a zona dinâmica
        self.lbl_quant.grid_remove(); self.ent_quant.grid_remove()
        self.lbl_altura.grid_remove(); self.ent_altura.grid_remove()
        self.lbl_perc.grid_remove(); self.ent_perc.grid_remove()
        self.frm_sls_checklist.grid_remove()

        if tech == "SLS":
            # 1. Desenha os campos numéricos da SLS
            self.lbl_altura.grid(row=6, column=0, padx=15, pady=5, sticky="e")
            self.ent_altura.grid(row=6, column=1, columnspan=2, padx=15, pady=5, sticky="ew")
            self.lbl_perc.grid(row=7, column=0, padx=15, pady=5, sticky="e")
            self.ent_perc.grid(row=7, column=1, columnspan=2, padx=15, pady=5, sticky="ew")
            
            # 2. Injeta o novo painel horizontal de checklist na linha 8
            self.frm_sls_checklist.grid(row=8, column=0, columnspan=3, padx=15, pady=10, sticky="ew")
            
            # 3. Puxa as iniciais e o botão para baixo
            self.lbl_resp.grid(row=9, column=0, padx=15, pady=10, sticky="e")
            self.cmb_resp.grid(row=9, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
            self.btn_salvar.grid(row=10, column=0, columnspan=3, pady=20, padx=15, sticky="ew")
            
            # 4. Vai buscar automaticamente o lote da última produção SLS
            ultimo_lote = ProducaoService.obter_ultimo_lote_sls()
            self.ent_lote.delete(0, ctk.END)
            self.ent_lote.insert(0, ultimo_lote)
        else:
            # Layout padrão FDM/SLA
            self.lbl_quant.grid(row=6, column=0, padx=15, pady=10, sticky="e")
            self.ent_quant.grid(row=6, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
            self.lbl_resp.grid(row=7, column=0, padx=15, pady=10, sticky="e")
            self.cmb_resp.grid(row=7, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
            self.btn_salvar.grid(row=8, column=0, columnspan=3, pady=20, padx=15, sticky="ew")
        
        self.validar_restricoes_botao()

    def validar_restricoes_botao(self):
        """ Se o operador estiver em modo SLS e desmarcar qualquer item, trava o botão """
        if self.cmb_tech.get() == "SLS":
            all_ok = all(var.get() for var in self.sls_vars.values())
            if not all_ok:
                self.btn_salvar.configure(state="disabled", fg_color="gray60")
                return
        self.btn_salvar.configure(state="normal", fg_color="#28a745")

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
        lote_atual = ""
        escala_atual = "1.000"
        
        if tech == "SLS":
            try:
                altura_c = float(self.ent_altura.get().strip().replace(',', '.'))
                perc_p = float(self.ent_perc.get().strip().replace(',', '.'))
                q_maq = ProducaoService.calcular_consumo_sls(altura_c, perc_p)
                lote_atual = self.ent_lote.get().strip()
                escala_atual = self.ent_escala.get().strip()
                
                if not lote_atual:
                    messagebox.showerror("Erro", "O campo Lote do Pó é obrigatório para tecnologia SLS.")
                    return
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
            "estado": "Em Andamento", "erro": "",
            "lote_po": lote_atual, "fator_escala": escala_atual # Chaves salvas na raiz do dicionário
        }
        
        logs.append(novo_log)
        JSONManager.salvar(logs, ARQUIVO_LOGS)
        
        messagebox.showinfo("Sucesso", "Produção SLS salva na base de dados JSON!")
        
        # Limpeza e reset dos campos e variáveis
        self.ent_tempo.delete(0, tk.END)
        if tech == "SLS":
            self.ent_altura.delete(0, tk.END); self.ent_perc.delete(0, tk.END)
            for var in self.sls_vars.values(): var.set(True) # Força voltar a True
        else:
            self.ent_quant.delete(0, tk.END)
        
        self.mudar_tecnologia(tech)