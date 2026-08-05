import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import os
from database.json_manager import JSONManager
from services.pedido_service import PedidoService

class ProducaoTab:
    def __init__(self, parent_frame, f_padrao, f_titulo, master_app=None):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.f_titulo = f_titulo
        self.master_app = master_app
        
        # 1. Variáveis de estado
        self.pedidos_vinculados = []
        self.parent.configure(fg_color="#f0f2f5") 

        # 2. Construir Interface
        self.construir_layout()

        # 3. Disparar estado inicial (que chama o atualizar_combos automaticamente)
        self.ao_mudar_tecnologia("FDM")

    def construir_layout(self):
        frm = ctk.CTkFrame(self.parent, fg_color="white", corner_radius=12, border_width=1, border_color="#e0e0e0")
        frm.pack(fill="both", expand=True, padx=20, pady=20)
        frm.columnconfigure(1, weight=1)

        # 0. Tecnologia AM
        ctk.CTkLabel(frm, text="Tecnologia AM:", font=self.f_padrao, text_color="gray30").grid(row=0, column=0, padx=15, pady=10, sticky="e")
        self.cmb_tech = ctk.CTkComboBox(frm, values=["FDM", "SLA", "SLS"], width=250, font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black", button_color="#1f538d", state="readonly", command=self.ao_mudar_tecnologia)
        self.cmb_tech.grid(row=0, column=1, padx=15, pady=10, sticky="w")

        # 1. Vincular Pedidos Abertos (N:N)
        ctk.CTkLabel(frm, text="Vincular Pedido(s):", font=self.f_padrao, text_color="gray30").grid(row=1, column=0, padx=15, pady=10, sticky="e")
        
        frm_pedidos_vinc = ctk.CTkFrame(frm, fg_color="transparent")
        frm_pedidos_vinc.grid(row=1, column=1, columnspan=2, padx=15, pady=10, sticky="ew")

        self.ent_pedidos_sel = ctk.CTkEntry(frm_pedidos_vinc, font=self.f_padrao, fg_color="#f0f2f5", border_color="gray80", text_color="black")
        self.ent_pedidos_sel.insert(0, "Nenhum pedido selecionado")
        self.ent_pedidos_sel.configure(state="readonly")
        self.ent_pedidos_sel.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkButton(frm_pedidos_vinc, text="📋 Selecionar Pedidos", width=160, fg_color="#1f538d", hover_color="#143a63", text_color="white", font=self.f_padrao, command=self.abrir_pop_up_selecao_pedidos).pack(side="right")

        # 2. Máquina Destino
        ctk.CTkLabel(frm, text="Máquina Destino:", font=self.f_padrao, text_color="gray30").grid(row=2, column=0, padx=15, pady=10, sticky="e")
        self.cmb_maq = ctk.CTkComboBox(frm, values=["A carregar..."], width=250, font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black", button_color="#1f538d", state="readonly")
        self.cmb_maq.grid(row=2, column=1, padx=15, pady=10, sticky="w")

        # 3. Tempo Máquina
        ctk.CTkLabel(frm, text="Tempo Máquina (HH:MM):", font=self.f_padrao, text_color="gray30").grid(row=3, column=0, padx=15, pady=10, sticky="e")
        self.ent_tempo = ctk.CTkEntry(frm, placeholder_text="02:30", font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black", width=250)
        self.ent_tempo.grid(row=3, column=1, padx=15, pady=10, sticky="w")
        self.ent_tempo.bind("<KeyRelease>", lambda e: self.mascara_tempo(e, self.ent_tempo))

        # --- CAMPOS DINÂMICOS DE CONSUMO ---
        self.lbl_quant = ctk.CTkLabel(frm, text="Quantidade (g/ml):", font=self.f_padrao, text_color="gray30")
        self.ent_quant = ctk.CTkEntry(frm, placeholder_text="150.5", font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black", width=250)
        
        self.lbl_altura = ctk.CTkLabel(frm, text="Altura da Cuba (mm):", font=self.f_padrao, text_color="gray30")
        self.ent_altura = ctk.CTkEntry(frm, placeholder_text="470", font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black", width=250)
        
        self.lbl_perc = ctk.CTkLabel(frm, text="% de Pó Novo:", font=self.f_padrao, text_color="gray30")
        self.ent_perc = ctk.CTkEntry(frm, placeholder_text="0.3", font=self.f_padrao, fg_color="white", border_color="gray80", text_color="black", width=250)

        # --- BLOCO EXCLUSIVO SLS ---
        self.frm_sls_checklist = ctk.CTkFrame(frm, fg_color="#f8f9fa", corner_radius=10, border_width=1, border_color="#e0e0e0")
        ctk.CTkLabel(self.frm_sls_checklist, text="⚙️ Parâmetros Básicos e Checklist Crítico SLS", font=("Arial", 12, "bold"), text_color="#1f538d").grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(10, 5))

        self.chk_var_lote = tk.BooleanVar(value=False)
        self.chk_lote = ctk.CTkCheckBox(self.frm_sls_checklist, text="Mesmo lote da produção anterior?", font=("Arial", 11, "bold"), variable=self.chk_var_lote, command=self.preencher_lote_anterior)
        self.chk_lote.grid(row=1, column=0, columnspan=3, padx=15, pady=(5, 10), sticky="w") 
        
        ctk.CTkLabel(self.frm_sls_checklist, text="Lote do Pó:", font=self.f_padrao, text_color="gray30").grid(row=2, column=0, padx=15, pady=5, sticky="w")
        self.ent_lote = ctk.CTkEntry(self.frm_sls_checklist, width=200, fg_color="white", border_color="gray80", text_color="black")
        self.ent_lote.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="w")

        self.sls_vars = {
            "slicefix": tk.BooleanVar(value=False), "po_suficiente": tk.BooleanVar(value=False), "abastecimento": tk.BooleanVar(value=False),
            "home_pistao": tk.BooleanVar(value=False), "home_rolo": tk.BooleanVar(value=False), "z_adicional": tk.BooleanVar(value=False),
            "chiller": tk.BooleanVar(value=False), "ac": tk.BooleanVar(value=False), "pre_aquecimento": tk.BooleanVar(value=False)
        }

        checks_config = [
            ("SliceFix OK", "slicefix", 3, 0), ("Quant. de pó suficiente", "po_suficiente", 3, 1), ("Abastecim/ de pó ligado", "abastecimento", 3, 2),
            ("Homing do Pistão", "home_pistao", 4, 0), ("Homing da Rolo", "home_rolo", 4, 1), ("Z adicional no topo", "z_adicional", 4, 2),
            ("Chiller ligado", "chiller", 5, 0), ("AC ligado", "ac", 5, 1), ("Pre-aquecimento", "pre_aquecimento", 5, 2)
        ]

        for text, key, row, col in checks_config:
            ctk.CTkCheckBox(self.frm_sls_checklist, text=text, font=("Arial", 11), variable=self.sls_vars[key]).grid(row=row, column=col, padx=15, pady=6, sticky="w")

        # Botão Guardar
        self.btn_salvar = ctk.CTkButton(frm, text="🚀 INICIAR FABRICO", fg_color="#28a745", hover_color="#218838", height=45, font=self.f_titulo, command=self.gravar_producao)

    def ao_mudar_tecnologia(self, escolha=None):
        """ Gere a visibilidade dos campos e recarrega máquinas e pedidos """
        tech_atual = self.cmb_tech.get()

        # 1. Reset dos pedidos vinculados
        self.pedidos_vinculados = []
        self.ent_pedidos_sel.configure(state="normal")
        self.ent_pedidos_sel.delete(0, "end")
        self.ent_pedidos_sel.insert(0, "Nenhum pedido selecionado")
        self.ent_pedidos_sel.configure(state="readonly")

        # 2. Esconde tudo
        self.lbl_quant.grid_forget()
        self.ent_quant.grid_forget()
        self.lbl_altura.grid_forget()
        self.ent_altura.grid_forget()
        self.lbl_perc.grid_forget()
        self.ent_perc.grid_forget()
        self.frm_sls_checklist.grid_forget()
        self.btn_salvar.grid_forget()

        # 3. Mostra consoante a tecnologia
        if tech_atual in ["FDM", "SLA"]:
            self.lbl_quant.grid(row=4, column=0, padx=15, pady=10, sticky="e")
            self.ent_quant.grid(row=4, column=1, padx=15, pady=10, sticky="w")
            self.btn_salvar.grid(row=5, column=0, columnspan=3, padx=15, pady=20, sticky="ew")
        elif tech_atual == "SLS":
            self.lbl_altura.grid(row=4, column=0, padx=15, pady=10, sticky="e")
            self.ent_altura.grid(row=4, column=1, padx=15, pady=10, sticky="w")
            self.lbl_perc.grid(row=5, column=0, padx=15, pady=10, sticky="e")
            self.ent_perc.grid(row=5, column=1, padx=15, pady=10, sticky="w")
            self.frm_sls_checklist.grid(row=6, column=0, columnspan=3, padx=15, pady=10, sticky="ew")
            self.btn_salvar.grid(row=7, column=0, columnspan=3, padx=15, pady=20, sticky="ew")

        # 4. Atualiza as máquinas
        self.atualizar_combos()

    def atualizar_combos(self):
        """ Carrega máquinas de forma segura a partir de parque_maquinas.json """
        if not hasattr(self, 'cmb_maq'): return
        
        tech_atual = self.cmb_tech.get()
        
        # Constrói o caminho absoluto para a tua pasta 'data'
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Agora aponta diretamente para o ficheiro correto!
        caminho_final = os.path.join(base_dir, "data", "parque_maquinas.json")
            
        if not os.path.exists(caminho_final):
            self.cmb_maq.configure(values=["Ficheiro parque_maquinas.json não encontrado"])
            self.cmb_maq.set("Sem dados")
            return

        try:
            impressoras = JSONManager.carregar(caminho_final)
            maquinas_compativeis = []
            
            for imp in impressoras:
                if isinstance(imp, dict):
                    # Tenta ler do dicionário
                    t = imp.get("tecnologia", imp.get("tech", tech_atual)) 
                    nome = imp.get("nome", imp.get("modelo", "Desconhecida"))
                    st = imp.get("status", imp.get("estado", "Ativa"))
                    
                    if t == tech_atual and st not in ["Inativa", "Manutenção"]:
                        maquinas_compativeis.append(nome)
                elif isinstance(imp, str):
                    # Se for só uma string simples
                    maquinas_compativeis.append(imp)

            if maquinas_compativeis:
                self.cmb_maq.configure(values=maquinas_compativeis)
                self.cmb_maq.set(maquinas_compativeis[0])
            else:
                self.cmb_maq.configure(values=[f"Sem máquinas p/ {tech_atual}"])
                self.cmb_maq.set(f"Sem p/ {tech_atual}")
                
        except Exception as e:
            self.cmb_maq.configure(values=["Erro ao ler ficheiro"])
            self.cmb_maq.set("Erro")
            print(f"Erro em atualizar_combos: {e}")

    def abrir_pop_up_selecao_pedidos(self):
        tech_atual = self.cmb_tech.get()
        pedidos_db = PedidoService.obter_todos()
        
        pedidos_compativeis = [
            p for p in pedidos_db 
            if p.get("estado", p.get("status", "")) in ["Pendente", "Em Andamento"]
            and p.get("tecnologia") == tech_atual
        ]

        if not pedidos_compativeis:
            messagebox.showinfo("Aviso", f"Não existem pedidos em aberto para a tecnologia {tech_atual}.")
            return

        top = ctk.CTkToplevel(self.parent.winfo_toplevel())
        top.title(f"Selecionar Pedidos ({tech_atual})")
        top.geometry("600x480")
        top.configure(fg_color="#fcfcfc")
        top.transient(self.parent.winfo_toplevel())
        top.grab_set()

        ctk.CTkLabel(top, text=f"Pedidos Abertos ({tech_atual}):", font=("Arial", 13, "bold"), text_color="#1f538d").pack(pady=(15, 5))
        ctk.CTkLabel(top, text="Nota: Só é possível agrupar pedidos do mesmo material.", font=("Arial", 10, "italic"), text_color="gray40").pack(pady=(0, 10))

        scroll_frame = ctk.CTkScrollableFrame(top, fg_color="white", border_width=1, border_color="#e0e0e0", corner_radius=8)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.dict_checks_pedidos = []
        ids_ja_selecionados = list(self.pedidos_vinculados)

        def extrair_materiais_pedido(p):
            mats = set()
            for peca in p.get("pecas", []):
                if peca.get("material"): mats.add(peca.get("material"))
            if not mats and p.get("material"): mats.add(p.get("material"))
            return list(mats)

        def reavaliar_bloqueio_materiais():
            mats_ativos = set()
            for item in self.dict_checks_pedidos:
                if item["var"].get(): mats_ativos.update(item["materiais"])

            for item in self.dict_checks_pedidos:
                if not mats_ativos:
                    item["widget"].configure(state="normal", text_color="black")
                else:
                    if any(m in mats_ativos for m in item["materiais"]):
                        item["widget"].configure(state="normal", text_color="black")
                    else:
                        item["var"].set(False)
                        item["widget"].configure(state="disabled", text_color="gray60")

        for p in pedidos_compativeis:
            id_p = p.get("id", p.get("id_pedido"))
            nr_proj = p.get("nr_projeto", p.get("projeto", "S/N"))
            mats = extrair_materiais_pedido(p)
            mat_str = ", ".join(mats) if mats else "N/A"
            
            label_text = f"ID #{id_p} | Proj: {nr_proj} | Mat: {mat_str}"

            var = tk.BooleanVar(value=(id_p in ids_ja_selecionados))
            chk = ctk.CTkCheckBox(scroll_frame, text=label_text, variable=var, font=("Arial", 11), command=reavaliar_bloqueio_materiais)
            chk.pack(anchor="w", padx=15, pady=8)

            self.dict_checks_pedidos.append({"id": id_p, "var": var, "widget": chk, "materiais": mats, "objeto": p})

        reavaliar_bloqueio_materiais()

        def confirmar_selecao():
            selecionados = [item for item in self.dict_checks_pedidos if item["var"].get()]
            self.ent_pedidos_sel.configure(state="normal")
            self.ent_pedidos_sel.delete(0, "end")
            
            if not selecionados:
                self.pedidos_vinculados = []
                self.ent_pedidos_sel.insert(0, "Nenhum pedido selecionado")
            else:
                self.pedidos_vinculados = [item["id"] for item in selecionados]
                ids_str = ", ".join([f"#{item['id']}" for item in selecionados])
                self.ent_pedidos_sel.insert(0, f"Pedidos Vinculados: {ids_str}")
                
            self.ent_pedidos_sel.configure(state="readonly")
            top.destroy()

        ctk.CTkButton(top, text="CONFIRMAR SELEÇÃO", fg_color="#28a745", hover_color="#218838", font=("Arial", 12, "bold"), height=40, command=confirmar_selecao).pack(fill="x", padx=20, pady=15)

    def mascara_tempo(self, event, entry):
        val = entry.get().replace(":", "")
        if not val.isdigit():
            entry.delete(0, tk.END)
            return
        if len(val) > 4: val = val[:4]
        if len(val) >= 3:
            formatted = f"{val[:2]}:{val[2:]}"
            entry.delete(0, tk.END)
            entry.insert(0, formatted)

    def gravar_producao(self):
        # 1. VALIDAÇÕES
        if not self.pedidos_vinculados:
            messagebox.showwarning("Aviso", "Por favor, vincule pelo menos um pedido à produção.")
            return

        tempo = self.ent_tempo.get().strip()
        if not tempo or len(tempo) < 5:
            messagebox.showwarning("Aviso", "Introduza um tempo de máquina válido (HH:MM).")
            return

        tech = self.cmb_tech.get()
        maq = self.cmb_maq.get()

        if maq.startswith("Sem máquinas") or maq == "A carregar..." or maq.startswith("Erro"):
            messagebox.showwarning("Aviso", "Selecione uma máquina válida antes de iniciar o fabrico.")
            return

        from datetime import datetime
        import os
        from database.json_manager import JSONManager
        
        # 2. CAMINHOS DOS FICHEIROS EXATOS (Baseados no repositório)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        caminho_producoes = os.path.join(base_dir, "data", "producao_i3D.json") # O ficheiro correto!
        caminho_pedidos = os.path.join(base_dir, "data", "pedidos.json")

        # 3. GUARDAR A PRODUÇÃO NO FICHEIRO producao_i3D.json
        producoes = JSONManager.carregar(caminho_producoes) if os.path.exists(caminho_producoes) else []
        
        # Procura o último ID (trata casos onde o ID pode ser string ou int)
        try:
            novo_id = max([int(p.get("id", p.get("id_producao", 0))) for p in producoes]) + 1 if producoes else 1
        except (ValueError, TypeError):
            novo_id = len(producoes) + 1

        nova_producao = {
            "id": novo_id,
            "data_inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tecnologia": tech,
            "maquina": maq,
            "tempo_estimado": tempo,
            "pedidos_vinculados": self.pedidos_vinculados,
            "estado": "A Imprimir",
            "operador": "CEiiA/i3D" 
        }

        # Guardar parâmetros específicos da tecnologia
        if tech in ["FDM", "SLA"]:
            if hasattr(self, 'ent_quant'):
                nova_producao["quantidade_consumida"] = self.ent_quant.get().strip()
        elif tech == "SLS":
            if hasattr(self, 'ent_altura'):
                nova_producao["altura_cuba"] = self.ent_altura.get().strip()
                nova_producao["percentagem_po_novo"] = self.ent_perc.get().strip()
                nova_producao["lote_po"] = self.ent_lote.get().strip()
                nova_producao["checklist_seguranca"] = {k: v.get() for k, v in self.sls_vars.items()}

        producoes.append(nova_producao)
        JSONManager.salvar(producoes, caminho_producoes)

        # 4. ATUALIZAR OS PEDIDOS PARA "Em Andamento"
        if os.path.exists(caminho_pedidos):
            pedidos = JSONManager.carregar(caminho_pedidos)
            modificado = False
            for p in pedidos:
                if p.get("id", p.get("id_pedido")) in self.pedidos_vinculados:
                    p["estado"] = "Em Andamento"
                    if "status" in p:  
                        p["status"] = "Em Andamento"
                    modificado = True
            
            if modificado:
                JSONManager.salvar(pedidos, caminho_pedidos)

        messagebox.showinfo("Sucesso", f"Produção #{novo_id} iniciada com sucesso na máquina {maq}!\n\nDados guardados em producao_i3D.json.")
        
        # 5. LIMPAR O FORMULÁRIO
        self.ao_mudar_tecnologia(tech)
        self.ent_tempo.delete(0, 'end')
        if hasattr(self, 'ent_quant'): self.ent_quant.delete(0, 'end')
        if hasattr(self, 'ent_altura'): self.ent_altura.delete(0, 'end')
        if hasattr(self, 'ent_perc'): self.ent_perc.delete(0, 'end')
        if hasattr(self, 'ent_lote'): self.ent_lote.delete(0, 'end')

    def preencher_lote_anterior(self):
        """ Vai buscar o último lote de SLS registado no producao_i3D.json """
        if self.chk_var_lote.get():
            import os
            from database.json_manager import JSONManager
            
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            caminho_producoes = os.path.join(base_dir, "data", "producao_i3D.json")
            
            if os.path.exists(caminho_producoes):
                producoes = JSONManager.carregar(caminho_producoes)
                # Filtra apenas produções SLS que tenham um lote preenchido
                lotes_sls = [p.get("lote_po") for p in producoes if p.get("tecnologia") == "SLS" and p.get("lote_po")]
                
                if lotes_sls:
                    ultimo_lote = lotes_sls[-1] # O último da lista
                    self.ent_lote.delete(0, 'end')
                    self.ent_lote.insert(0, ultimo_lote)
                    return
            
            # Se falhar ou não encontrar histórico
            self.chk_var_lote.set(False)
            messagebox.showinfo("Info", "Nenhum registo de lote de pó anterior encontrado.")
        else:
            # Limpa o campo se o utilizador desmarcar a caixa
            self.ent_lote.delete(0, 'end')