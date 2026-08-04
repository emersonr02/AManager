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
        
        # 1. Variáveis de memória primeiro
        self.pedidos_vinculados = [] 
        self.parent.configure(fg_color="#f0f2f5") 

        # 2. Constrói a interface e os componentes (comboboxes, entradas, etc.)
        self.construir_layout()

        # 3. Popula as comboboxes com os dados das bases de dados (JSON)
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

    def obter_usuario_windows(self):
        """ Captura as credenciais do utilizador logado no sistema operativo """
        try:
            return os.getlogin()
        except Exception:
            return "Operador_Desconhecido"

    def construir_layout(self):
        # Frame Principal
        frm = ctk.CTkFrame(self.parent, fg_color="white", corner_radius=12, border_width=1, border_color="#e0e0e0")
        frm.pack(fill="both", expand=True, padx=20, pady=20)
        frm.columnconfigure(1, weight=1)

        # 1. Vincular Pedidos Abertos (N:N - Estilo Padronizado)
        ctk.CTkLabel(frm, text="Vincular Pedido(s) Aberto(s):", font=self.f_padrao, text_color="gray30").grid(row=1, column=0, padx=15, pady=10, sticky="e")
        
        frm_pedidos_vinc = ctk.CTkFrame(frm, fg_color="transparent")
        frm_pedidos_vinc.grid(row=1, column=1, columnspan=2, padx=15, pady=10, sticky="ew")

        # Entrada readonly que mostra os pedidos selecionados
        self.ent_pedidos_sel = ctk.CTkEntry(frm_pedidos_vinc, font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black")
        self.ent_pedidos_sel.insert(0, "Nenhum pedido selecionado")
        self.ent_pedidos_sel.configure(state="readonly")
        self.ent_pedidos_sel.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Botão com o azul padrão (#1f538d) para abrir a lista múltipla
        ctk.CTkButton(frm_pedidos_vinc, text="📋 Selecionar Pedidos", width=140, fg_color="#1f538d", hover_color="#143a63", text_color="white", font=self.f_padrao, command=self.abrir_pop_up_selecao_pedidos).pack(side="right")

        # 1. Vincular Pedido Aberto (A nova Select Box)
        ctk.CTkLabel(frm, text="Vincular Pedido Aberto:", font=("Arial", 11, "bold"), text_color="gray40").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.cmb_pedido_pendente = ctk.CTkComboBox(frm, values=["Selecione a Tecnologia primeiro..."], width=350, fg_color="#f0f2f5", text_color="black", command=self.ao_selecionar_pedido_aberto)
        self.cmb_pedido_pendente.grid(row=1, column=1, columnspan=2, padx=10, pady=10, sticky="w")

        # 2. Máquina Destino
        ctk.CTkLabel(frm, text="Máquina Destino:", font=self.f_padrao, text_color="gray30").grid(row=2, column=0, padx=15, pady=10, sticky="e")
        self.cmb_maq = ctk.CTkComboBox(frm, values=[], width=250, font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black", button_color="#1f538d", state="readonly")
        self.cmb_maq.grid(row=2, column=1, padx=15, pady=10, sticky="w")

        # 3. Pasta do Projeto
        ctk.CTkLabel(frm, text="Pasta do Projeto (Rede/Local):", font=self.f_padrao, text_color="gray30").grid(row=3, column=0, padx=15, pady=10, sticky="e")
        self.ent_pasta = ctk.CTkEntry(frm, placeholder_text="\\\\ceiia.com\\PPS\\...", font=self.f_padrao, fg_color="#f0f2f5", border_color="gray80", text_color="black")
        self.ent_pasta.grid(row=3, column=1, padx=15, pady=10, sticky="ew")
        ctk.CTkButton(frm, text="Mapear", width=100, fg_color="#f0f2f5", text_color="black", hover_color="#e0e0e0", font=self.f_padrao, command=self.mapear_diretorio).grid(row=3, column=2, padx=15, pady=10)

        # 4. ID - Projeto
        ctk.CTkLabel(frm, text="ID - Projeto:", font=self.f_padrao, text_color="gray30").grid(row=4, column=0, padx=15, pady=10, sticky="e")
        frm_proj = ctk.CTkFrame(frm, fg_color="transparent")
        frm_proj.grid(row=4, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
        self.cmb_proj = ctk.CTkComboBox(frm_proj, values=[], font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black", button_color="#1f538d", state="readonly")
        self.cmb_proj.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(frm_proj, text="⚙️ Gerir", width=70, fg_color="#f0f2f5", text_color="black", hover_color="#e0e0e0", font=self.f_padrao, command=lambda: JanelaGestaoSimples(self.master_app, "Gestão de Projetos", "ID (6 dígitos)", "Nome do Projeto", ARQUIVO_PROJETOS, self.atualizar_combos)).pack(side="right")

        # 5. Material e Fabricante
        ctk.CTkLabel(frm, text="Material e Fabricante:", font=self.f_padrao, text_color="gray30").grid(row=5, column=0, padx=15, pady=10, sticky="e")
        frm_mat = ctk.CTkFrame(frm, fg_color="transparent")
        frm_mat.grid(row=5, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
        self.cmb_mat = ctk.CTkComboBox(frm_mat, values=[], font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black", button_color="#1f538d", state="readonly")
        self.cmb_mat.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(frm_mat, text="⚙️ Gerir", width=70, fg_color="#f0f2f5", text_color="black", hover_color="#e0e0e0", font=self.f_padrao, command=lambda: JanelaGestaoSimples(self.master_app, "Gestão de Materiais", "Nome do Material", "Fabricante", ARQUIVO_MATERIAIS, self.atualizar_combos)).pack(side="right")

        # 6. Tempo Máquina
        ctk.CTkLabel(frm, text="Tempo Máquina (HH:MM):", font=self.f_padrao, text_color="gray30").grid(row=6, column=0, padx=15, pady=10, sticky="e")
        self.ent_tempo = ctk.CTkEntry(frm, placeholder_text="02:30", font=self.f_padrao, fg_color="#f0f2f5", border_color="gray80", text_color="black")
        self.ent_tempo.grid(row=6, column=1, columnspan=2, padx=15, pady=10, sticky="ew")
        self.ent_tempo.bind("<KeyRelease>", lambda e: self.mascara_tempo(e, self.ent_tempo))

        # 7. Campos Dinâmicos Genéricos (Sem grid fixo, geridos pelo mudar_tecnologia)
        self.lbl_quant = ctk.CTkLabel(frm, text="Quantidade (g/ml):", font=self.f_padrao, text_color="gray30")
        self.ent_quant = ctk.CTkEntry(frm, placeholder_text="150.5", font=self.f_padrao, fg_color="#f0f2f5", border_color="gray80", text_color="black")
        
        self.lbl_altura = ctk.CTkLabel(frm, text="Altura da Cuba (mm):", font=self.f_padrao, text_color="gray30")
        self.ent_altura = ctk.CTkEntry(frm, placeholder_text="470", font=self.f_padrao, fg_color="#f0f2f5", border_color="gray80", text_color="black")
        
        self.lbl_perc = ctk.CTkLabel(frm, text="% de Pó Novo:", font=self.f_padrao, text_color="gray30")
        self.ent_perc = ctk.CTkEntry(frm, placeholder_text="0.3", font=self.f_padrao, fg_color="#f0f2f5", border_color="gray80", text_color="black")

        # ----------------------------------------------------
        # --- BLOCO EXCLUSIVO SLS (CHECKLIST DE SEGURANÇA) ---
        # ----------------------------------------------------
        self.frm_sls_checklist = ctk.CTkFrame(frm, fg_color="#f8f9fa", corner_radius=10, border_width=1, border_color="#e0e0e0")
        
        ctk.CTkLabel(self.frm_sls_checklist, text="⚙️ Parâmetros Básicos e Checklist Crítico SLS", font=("Arial", 12, "bold"), text_color="#1f538d").grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(10, 5))

        # Checkbox Inteligente para o Lote do Pó
        self.chk_var_lote = tk.BooleanVar(value=False)
        self.chk_lote = ctk.CTkCheckBox(self.frm_sls_checklist, text="Mesmo lote da produção anterior?", font=("Arial", 11, "bold"), variable=self.chk_var_lote, command=self.preencher_lote_automatico)
        self.chk_lote.grid(row=1, column=0, columnspan=2, padx=15, pady=(5, 10), sticky="w")

        ctk.CTkLabel(self.frm_sls_checklist, text="Lote do Pó:", font=self.f_padrao, text_color="gray30").grid(row=2, column=0, padx=15, pady=5, sticky="w")
        self.ent_lote = ctk.CTkEntry(self.frm_sls_checklist, width=200, fg_color="white", border_color="gray80", text_color="black")
        self.ent_lote.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="w")

        # Variáveis booleanas (TODAS FALSE POR DEFEITO)
        self.sls_vars = {
            "slicefix": tk.BooleanVar(value=False),
            "po_suficiente": tk.BooleanVar(value=False),
            "abastecimento": tk.BooleanVar(value=False),
            "home_pistao": tk.BooleanVar(value=False),
            "home_rolo": tk.BooleanVar(value=False),
            "z_adicional": tk.BooleanVar(value=False),
            "chiller": tk.BooleanVar(value=False),
            "ac": tk.BooleanVar(value=False),
            "pre_aquecimento": tk.BooleanVar(value=False),
        }

        # Grid de Checkboxes
        checks_config = [
            ("SliceFix OK", "slicefix", 3, 0),
            ("Quant. de pó suficiente", "po_suficiente", 3, 1),
            ("Abastecim/ de pó ligado", "abastecimento", 3, 2),
            ("Homing do Pistão", "home_pistao", 4, 0),
            ("Homing da Rolo", "home_rolo", 4, 1),
            ("Z adicional no topo", "z_adicional", 4, 2),
            ("Chiller ligado", "chiller", 5, 0),
            ("AC ligado", "ac", 5, 1),
            ("Pre-aquecimento", "pre_aquecimento", 5, 2),
        ]

        for text, key, row, col in checks_config:
            chk = ctk.CTkCheckBox(self.frm_sls_checklist, text=text, font=("Arial", 11), variable=self.sls_vars[key], command=self.validar_restricoes_botao)
            chk.grid(row=row, column=col, padx=15, pady=6, sticky="w")
        # ----------------------------------------------------

        # Operador e Botão Salvar (Geridos pelo mudar_tecnologia, criados aqui)
        self.lbl_resp = ctk.CTkLabel(frm, text="Operador (Autenticado):", font=self.f_padrao, text_color="gray30")
        self.ent_resp = ctk.CTkEntry(frm, font=self.f_padrao, fg_color="#e9ecef", border_color="gray80", text_color="gray30")
        
        self.btn_salvar = ctk.CTkButton(frm, text="🚀 INICIAR FABRICO", fg_color="gray60", hover_color="#218838", state="disabled", height=45, font=self.f_titulo, command=self.gravar_producao)
        
        # Arranca a interface forçando o carregamento do layout base
        self.mudar_tecnologia("FDM")

    def preencher_lote_automatico(self):
        """ Injeta o lote anterior se a checkbox for marcada """
        self.ent_lote.delete(0, ctk.END)
        if self.chk_var_lote.get():
            ultimo_lote = ProducaoService.obter_ultimo_lote_sls()
            self.ent_lote.insert(0, ultimo_lote)

    def atualizar_combos(self, *args):
        if not hasattr(self, 'cmb_tech'):
            return
        tech = self.cmb_tech.get()
        maquinas_ativas = MaquinaService.obter_ativas_por_tecnologia(tech)
        self.cmb_maq.configure(values=maquinas_ativas)
        self.cmb_maq.set(maquinas_ativas[0] if maquinas_ativas else "Nenhuma Ativa")
        
        self.cmb_proj.configure(values=JSONManager.carregar(ARQUIVO_PROJETOS))
        self.cmb_mat.configure(values=JSONManager.carregar(ARQUIVO_MATERIAIS))
        
        # Injeção das credenciais na Entry bloqueada
        self.ent_resp.configure(state="normal")
        self.ent_resp.delete(0, tk.END)
        self.ent_resp.insert(0, self.obter_usuario_windows())
        self.ent_resp.configure(state="readonly")

    def mudar_tecnologia(self, tech_selecionada):
        # 1. GESTÃO DO LAYOUT (Checklist SLS vs Outras)
        # (Se já tinhas aqui lógica para esconder/mostrar campos da SLS, mantém-na!)
        if tech_selecionada == "SLS":
            self.frm_sls_checklist.grid(row=7, column=0, columnspan=3, padx=20, pady=10, sticky="ew")
        else:
            if hasattr(self, 'frm_sls_checklist'):
                self.frm_sls_checklist.grid_forget()

        # 2. O NOVO MOTOR "PULL" (Ler os pedidos abertos automaticamente)
        try:
            from services.pedido_service import PedidoService
            pedidos = PedidoService.obter_todos()
            
            # Filtra os pedidos que estão "Pendentes" e que coincidem com a tecnologia escolhida (FDM, SLA, SLS)
            pendentes = [
                p for p in pedidos 
                if p.get("estado", p.get("status", "")) == "Pendente" 
                and p.get("tecnologia") == tech_selecionada
            ]
            
            if pendentes:
                valores = ["Nenhum (Produção Manual)"]
                for p in pendentes:
                    id_ped = p.get("id", p.get("id_pedido"))
                    proj = p.get("nr_projeto", p.get("projeto", "S/N"))
                    mat = str(p.get("material") or "N/A")
                    valores.append(f"ID: {id_ped} | Proj: {proj} | Mat: {mat}")
                
                self.cmb_pedido_pendente.configure(values=valores)
                self.cmb_pedido_pendente.set(f"{len(pendentes)} Pedido(s) disponível(eis)...")
            else:
                self.cmb_pedido_pendente.configure(values=["Sem pedidos pendentes para esta tecnologia"])
                self.cmb_pedido_pendente.set("Sem pedidos pendentes")
                
        except Exception as e:
            print(f"Aviso: Erro a carregar pedidos dinâmicos: {e}")

    def validar_restricoes_botao(self):
        """ Controla o bloqueio do botão baseado nos checks desmarcados da SLS """
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
        
        if tech == "SLS":
            try:
                altura_c = float(self.ent_altura.get().strip().replace(',', '.'))
                perc_p = float(self.ent_perc.get().strip().replace(',', '.'))
                q_maq = ProducaoService.calcular_consumo_sls(altura_c, perc_p)
                lote_atual = self.ent_lote.get().strip()
                
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

        if not self.cmb_proj.get() or not self.ent_pasta.get() or "Nenhuma" in self.cmb_maq.get():
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
            "tecnologia": tech, "responsavel": self.ent_resp.get(),
            "estado": "Em Andamento", "erro": "",
            "lote_po": lote_atual,
            "pedidos_vinculados": getattr(self, "pedidos_vinculados", [])
        }
        
        logs.append(novo_log)
        JSONManager.salvar(logs, ARQUIVO_LOGS)
        
        # Atualiza os pedidos vinculados para "Em Andamento"
        pedidos_vinc = getattr(self, "pedidos_vinculados", [])
        if pedidos_vinc:
            from config.paths import ARQUIVO_PEDIDOS
            pedidos_db = JSONManager.carregar(ARQUIVO_PEDIDOS)
            mudou_pedido = False
            
            for p in pedidos_db:
                if p.get("id", p.get("id_pedido")) in pedidos_vinc:
                    p["status"] = "Em Andamento"
                    p["estado"] = "Em Andamento" # Dupla garantia de compatibilidade
                    mudou_pedido = True
                    
            if mudou_pedido:
                JSONManager.salvar(pedidos_db, ARQUIVO_PEDIDOS)
        # --- FIM DA RASTREABILIDADE ---
        
        messagebox.showinfo("Sucesso", "Produção registada e pedidos atualizados!")
        
        # (O código continua normalmente com a limpeza dos campos)
        self.pedidos_vinculados = []
        self.ent_tempo.delete(0, tk.END)

    def ao_selecionar_pedido_aberto(self, selecao):
        if selecao.startswith("ID:"):
            # 1. Extrai o ID do texto (ex: "ID: 2 | Proj: ...")
            id_str = selecao.split("|")[0].replace("ID:", "").strip()
            id_pedido = int(id_str)
            
            # 2. Vai buscar o pedido completo à base de dados
            from services.pedido_service import PedidoService
            pedidos = PedidoService.obter_todos()
            pedido_alvo = next((p for p in pedidos if p.get("id", p.get("id_pedido")) == id_pedido), None)
            
            if pedido_alvo:
                # 3. Guarda na memória para a rastreabilidade (fecho da Sprint 5)
                self.pedidos_vinculados = [id_pedido]
                
                # 4. Auto-preenche o Material
                mat = pedido_alvo.get("material")
                if mat and mat != "None":
                    # Se o material não estiver na lista atual da máquina, adiciona-o temporariamente
                    if hasattr(self, 'cmb_mat') and mat not in self.cmb_mat.cget("values"):
                        v = list(self.cmb_mat.cget("values"))
                        v.append(mat)
                        self.cmb_mat.configure(values=v)
                    self.cmb_mat.set(mat)
                
                # 5. Auto-preenche o Projeto (AGORA COM NOME)
                nr_proj = pedido_alvo.get("nr_projeto", pedido_alvo.get("projeto", ""))
                nome_proj = pedido_alvo.get("nome_projeto", "")
                
                # Se tiver nome, formata "257147 - PPS AquaFountain", senão fica só o número
                proj_formatado = f"{nr_proj} - {nome_proj}" if nome_proj else str(nr_proj)
                
                if proj_formatado:
                    if hasattr(self, 'cmb_proj') and proj_formatado not in self.cmb_proj.cget("values"):
                        v = list(self.cmb_proj.cget("values"))
                        v.append(proj_formatado)
                        self.cmb_proj.configure(values=v)
                    self.cmb_proj.set(proj_formatado)
                
                # 6. Auto-preenche a Pasta/Rede (se existir)
                link = pedido_alvo.get("link_arquivos")
                if link and hasattr(self, 'ent_pasta'):
                    self.ent_pasta.delete(0, "end")
                    self.ent_pasta.insert(0, link)
        else:
            # Se escolher "Nenhum", limpa o vínculo
            self.pedidos_vinculados = []
    
    def abrir_pop_up_selecao_pedidos(self):
        """ Pop-up modal com Checkboxes para seleção múltipla N:N """
        from services.pedido_service import PedidoService
        pedidos_db = PedidoService.obter_todos()
        
        # Filtra pedidos pendentes ou em andamento (que ainda têm peças por produzir)
        pedidos_abertos = [p for p in pedidos_db if p.get("estado", p.get("status", "")) in ["Pendente", "Em Andamento"]]

        if not pedidos_abertos:
            messagebox.showinfo("Aviso", "Não existem pedidos em aberto de momento.")
            return

        top = ctk.CTkToplevel(self.parent.winfo_toplevel())
        top.title("Selecionar Pedidos para esta Produção (N:N)")
        top.geometry("550x450")
        top.configure(fg_color="#fcfcfc")
        top.transient(self.parent.winfo_toplevel())
        top.grab_set()

        ctk.CTkLabel(top, text="Selecione um ou mais pedidos para agrupar:", font=("Arial", 13, "bold"), text_color="#1f538d").pack(pady=15)

        scroll_frame = ctk.CTkScrollableFrame(top, fg_color="white", border_width=1, border_color="#e0e0e0", corner_radius=8)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        # Guarda os dicionários com as variáveis de cada checkbox
        self.dict_checks_pedidos = []

        # IDs já selecionados previamente para manter os checks ativos
        ids_ja_selecionados = getattr(self, "pedidos_vinculados", [])

        for p in pedidos_abertos:
            id_p = p.get("id", p.get("id_pedido"))
            nr_proj = p.get("nr_projeto", p.get("projeto", "S/N"))
            nome_proj = p.get("nome_projeto", "")
            tech = p.get("tecnologia", "N/A")
            
            proj_str = f"{nr_proj} - {nome_proj}" if nome_proj else str(nr_proj)
            label_text = f"ID #{id_p} | Proj: {proj_str} | Tech: {tech}"

            var = tk.BooleanVar(value=(id_p in ids_ja_selecionados))
            chk = ctk.CTkCheckBox(scroll_frame, text=label_text, variable=var, font=("Arial", 11), text_color="black")
            chk.pack(anchor="w", padx=15, pady=8)

            self.dict_checks_pedidos.append({"id": id_p, "var": var, "objeto": p})

        def confirmar_selecao():
            selecionados = [item for item in self.dict_checks_pedidos if item["var"].get()]
            
            if not selecionados:
                self.pedidos_vinculados = []
                self.ent_pedidos_sel.configure(state="normal")
                self.ent_pedidos_sel.delete(0, "end")
                self.ent_pedidos_sel.insert(0, "Nenhum pedido selecionado")
                self.ent_pedidos_sel.configure(state="readonly")
            else:
                # Guarda a lista de IDs vinculados
                self.pedidos_vinculados = [item["id"] for item in selecionados]
                ids_str = ", ".join([f"#{item['id']}" for item in selecionados])
                
                self.ent_pedidos_sel.configure(state="normal")
                self.ent_pedidos_sel.delete(0, "end")
                self.ent_pedidos_sel.insert(0, f"Pedidos Vinculados: {ids_str}")
                self.ent_pedidos_sel.configure(state="readonly")

                # AUTO-PREENCHIMENTO COMBINADO (Consolida Projetos de múltiplos pedidos)
                primeiro_obj = selecionados[0]["objeto"]
                
                # 1. Atualiza Projeto (Concatena se forem projetos diferentes)
                projetos_unicos = list(set([f"{p['objeto'].get('nr_projeto')} - {p['objeto'].get('nome_projeto', '')}".strip(" -") for p in selecionados]))
                proj_final = " | ".join(projetos_unicos)
                
                if hasattr(self, 'cmb_proj'):
                    if proj_final not in self.cmb_proj.cget("values"):
                        v = list(self.cmb_proj.cget("values"))
                        v.append(proj_final)
                        self.cmb_proj.configure(values=v)
                    self.cmb_proj.set(proj_final)

                # 2. Atualiza Pasta / Link
                links = list(set([p['objeto'].get('link_arquivos', '') for p in selecionados if p['objeto'].get('link_arquivos')]))
                if links and hasattr(self, 'ent_pasta'):
                    self.ent_pasta.delete(0, "end")
                    self.ent_pasta.insert(0, " | ".join(links))

                # 3. Ajusta Tecnologia se for comum
                tech_ref = primeiro_obj.get("tecnologia")
                if hasattr(self, 'cmb_tech') and tech_ref:
                    self.cmb_tech.set(tech_ref)
                    self.mudar_tecnologia(tech_ref)

            top.destroy()

        ctk.CTkButton(top, text="CONFIRMAR SELEÇÃO", fg_color="#28a745", hover_color="#218838", font=("Arial", 12, "bold"), height=40, command=confirmar_selecao).pack(fill="x", padx=20, pady=15)