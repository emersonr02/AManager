import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import os
from services.pedido_service import PedidoService
from services.producao_service import ProducaoService
from services.maquina_service import MaquinaService
from services.template_service import TemplateService
from services.nc_service import NCService
from gui import theme

class ProducaoTab:
    def __init__(self, parent_frame, f_padrao, f_titulo, master_app=None):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.f_titulo = f_titulo
        self.master_app = master_app

        # 1. Variáveis de estado
        self.pedidos_vinculados = []
        self.parent.configure(fg_color=theme.BG)

        # 2. Construir Interface
        self.construir_layout()

        # 3. Disparar estado inicial (que chama o atualizar_combos automaticamente)
        self.ao_mudar_tecnologia("FDM")

    def _lbl_campo(self, parent, texto, row):
        ctk.CTkLabel(parent, text=texto.upper(), font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).grid(row=row, column=0, padx=15, pady=10, sticky="e")

    def construir_layout(self):
        theme.page_header(self.parent, "Chão de Fábrica", "Nova Produção").pack(fill="x", padx=24, pady=(22, 10))

        frm = ctk.CTkFrame(self.parent, fg_color=theme.SURFACE, corner_radius=theme.RADIUS_M, border_width=1, border_color=theme.BORDER)
        frm.pack(fill="both", expand=True, padx=24, pady=(0, 18))
        frm.columnconfigure(1, weight=0)
        frm.columnconfigure(2, weight=1)

        # 0. Tecnologia AM
        self._lbl_campo(frm, "Tecnologia AM", 0)
        self.cmb_tech = theme.combobox(frm, values=["FDM", "SLA", "SLS"], width=250, font=self.f_padrao, state="readonly", command=self.ao_mudar_tecnologia)
        self.cmb_tech.grid(row=0, column=1, padx=15, pady=10, sticky="w")

        # 0.5. Templates de produção — atalho para preencher os campos de um job recorrente
        self._lbl_campo(frm, "Usar Template", 1)
        frm_template = ctk.CTkFrame(frm, fg_color="transparent")
        frm_template.grid(row=1, column=1, columnspan=2, padx=15, pady=(0, 5), sticky="ew")

        self.cmb_template = theme.combobox(frm_template, values=["Nenhum"], width=280,
                                           font=self.f_padrao, state="readonly",
                                           command=self.aplicar_template)
        self.cmb_template.set("Nenhum")
        self.cmb_template.pack(side="left")

        theme.button_ghost(frm_template, text="💾 Guardar como Template", width=190,
                           command=self.abrir_guardar_template).pack(side="left", padx=(10, 0))

        # 1. Vincular Pedidos Abertos (N:N)
        self._lbl_campo(frm, "Vincular Pedido(s)", 2)

        frm_pedidos_vinc = ctk.CTkFrame(frm, fg_color="transparent")
        frm_pedidos_vinc.grid(row=2, column=1, columnspan=2, padx=15, pady=10, sticky="ew")

        self.ent_pedidos_sel = theme.entry(frm_pedidos_vinc, font=self.f_padrao)
        self.ent_pedidos_sel.insert(0, "Nenhum pedido selecionado")
        self.ent_pedidos_sel.configure(state="readonly")
        self.ent_pedidos_sel.pack(side="left", fill="x", expand=True, padx=(0, 10))

        theme.button_ghost(frm_pedidos_vinc, text="📋 Selecionar Pedidos", width=160, command=self.abrir_pop_up_selecao_pedidos).pack(side="right")

        # 2. Máquina Destino
        self._lbl_campo(frm, "Máquina Destino", 3)
        self.cmb_maq = theme.combobox(frm, values=["A carregar..."], width=250, font=self.f_padrao,
                                      state="readonly", command=self.ao_selecionar_maquina)
        self.cmb_maq.grid(row=3, column=1, padx=15, pady=10, sticky="w")

        # Alerta de NC recorrente — some por baixo do seletor de máquina
        # apenas quando há um problema não resolvido nessa máquina.
        self.lbl_alerta_recorrencia = ctk.CTkLabel(
            frm, text="", font=theme.font_body(10, "bold"), text_color=theme.WARNING,
            justify="left", wraplength=500)
        self.lbl_alerta_recorrencia.grid(row=3, column=2, padx=(0, 15), pady=10, sticky="w")

        # 3. Tempo Máquina
        self._lbl_campo(frm, "Tempo Máquina (HH:MM)", 4)
        self.ent_tempo = theme.entry(frm, placeholder_text="02:30", font=theme.font_mono(13), width=250)
        self.ent_tempo.grid(row=4, column=1, padx=15, pady=10, sticky="w")
        self.ent_tempo.bind("<KeyRelease>", lambda e: self.mascara_tempo(e, self.ent_tempo))

        # --- CAMPOS DINÂMICOS DE CONSUMO ---
        self.lbl_quant = ctk.CTkLabel(frm, text="QUANTIDADE (G/ML)", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED)
        self.ent_quant = theme.entry(frm, placeholder_text="150.5", font=theme.font_mono(13), width=250)

        self.lbl_altura = ctk.CTkLabel(frm, text="ALTURA DA CUBA (MM)", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED)
        self.ent_altura = theme.entry(frm, placeholder_text="470", font=theme.font_mono(13), width=250)

        self.lbl_perc = ctk.CTkLabel(frm, text="% DE PÓ NOVO", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED)
        self.ent_perc = theme.entry(frm, placeholder_text="0.3", font=theme.font_mono(13), width=250)

        # ====================================================
        # --- BLOCOS DE CHECKLISTS POR TECNOLOGIA ---
        # ====================================================

        checkbox_kwargs = dict(fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, checkmark_color=theme.WHITE, border_color=theme.TEXT_MUTED, text_color=theme.TEXT)

        # 1. BLOCO EXCLUSIVO FDM
        self.frm_fdm_checklist = ctk.CTkFrame(frm, fg_color=theme.SURFACE_ALT, corner_radius=theme.RADIUS_M, border_width=1, border_color=theme.BORDER)
        ctk.CTkLabel(self.frm_fdm_checklist, text="⚙️ Checklist Crítico FDM", font=theme.font_body(12, "bold"), text_color=theme.TEAL).grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(10, 5))

        self.fdm_vars = {
            "nivelamento_mesa": tk.BooleanVar(value=False),
            "analise_gcode": tk.BooleanVar(value=False),
            "qualidade_filamento": tk.BooleanVar(value=False)
        }

        ctk.CTkCheckBox(self.frm_fdm_checklist, text="NIVELAMENTO DA MESA", font=theme.font_body(11), variable=self.fdm_vars["nivelamento_mesa"], **checkbox_kwargs).grid(row=1, column=0, padx=15, pady=10, sticky="w")
        ctk.CTkCheckBox(self.frm_fdm_checklist, text="ANÁLISE GCODE", font=theme.font_body(11), variable=self.fdm_vars["analise_gcode"], **checkbox_kwargs).grid(row=1, column=1, padx=15, pady=10, sticky="w")
        ctk.CTkCheckBox(self.frm_fdm_checklist, text="QUALIDADE DO FILAMENTO", font=theme.font_body(11), variable=self.fdm_vars["qualidade_filamento"], **checkbox_kwargs).grid(row=1, column=2, padx=15, pady=10, sticky="w")

        # 2. BLOCO EXCLUSIVO SLA
        self.frm_sla_checklist = ctk.CTkFrame(frm, fg_color=theme.SURFACE_ALT, corner_radius=theme.RADIUS_M, border_width=1, border_color=theme.BORDER)
        ctk.CTkLabel(self.frm_sla_checklist, text="⚙️ Checklist Crítico SLA", font=theme.font_body(12, "bold"), text_color=theme.TEAL).grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(10, 5))

        self.sla_vars = {
            "limpeza_tanque": tk.BooleanVar(value=False),
            "limpeza_mesa": tk.BooleanVar(value=False),
            "qualidade_resina": tk.BooleanVar(value=False)
        }

        ctk.CTkCheckBox(self.frm_sla_checklist, text="LIMPEZA DO TANQUE", font=theme.font_body(11), variable=self.sla_vars["limpeza_tanque"], **checkbox_kwargs).grid(row=1, column=0, padx=15, pady=10, sticky="w")
        ctk.CTkCheckBox(self.frm_sla_checklist, text="LIMPEZA DA MESA", font=theme.font_body(11), variable=self.sla_vars["limpeza_mesa"], **checkbox_kwargs).grid(row=1, column=1, padx=15, pady=10, sticky="w")
        ctk.CTkCheckBox(self.frm_sla_checklist, text="QUALIDADE DA RESINA", font=theme.font_body(11), variable=self.sla_vars["qualidade_resina"], **checkbox_kwargs).grid(row=1, column=2, padx=15, pady=10, sticky="w")

        # 3. BLOCO EXCLUSIVO SLS
        self.frm_sls_checklist = ctk.CTkFrame(frm, fg_color=theme.SURFACE_ALT, corner_radius=theme.RADIUS_M, border_width=1, border_color=theme.BORDER)
        ctk.CTkLabel(self.frm_sls_checklist, text="⚙️ Parâmetros Básicos e Checklist Crítico SLS", font=theme.font_body(12, "bold"), text_color=theme.TEAL).grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(10, 5))

        self.chk_var_lote = tk.BooleanVar(value=False)
        self.chk_lote = ctk.CTkCheckBox(self.frm_sls_checklist, text="Mesmo lote da produção anterior?", font=theme.font_body(11, "bold"), variable=self.chk_var_lote, command=self.preencher_lote_anterior, **checkbox_kwargs)
        self.chk_lote.grid(row=1, column=0, columnspan=3, padx=15, pady=(5, 10), sticky="w")

        ctk.CTkLabel(self.frm_sls_checklist, text="LOTE DO PÓ", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).grid(row=2, column=0, padx=15, pady=5, sticky="w")
        self.ent_lote = theme.entry(self.frm_sls_checklist, width=200, font=theme.font_mono(12))
        self.ent_lote.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="w")

        self.sls_vars = {
            "slicefix": tk.BooleanVar(value=False), "po_suficiente": tk.BooleanVar(value=False), "abastecimento": tk.BooleanVar(value=False),
            "home_pistao": tk.BooleanVar(value=False), "home_rolo": tk.BooleanVar(value=False), "z_adicional": tk.BooleanVar(value=False),
            "chiller": tk.BooleanVar(value=False), "ac": tk.BooleanVar(value=False), "pre_aquecimento": tk.BooleanVar(value=False)
        }

        checks_config_sls = [
            ("SliceFix OK", "slicefix", 3, 0), ("Quant. de pó suficiente", "po_suficiente", 3, 1), ("Abastecim/ de pó ligado", "abastecimento", 3, 2),
            ("Homing do Pistão", "home_pistao", 4, 0), ("Homing da Rolo", "home_rolo", 4, 1), ("Z adicional no topo", "z_adicional", 4, 2),
            ("Chiller ligado", "chiller", 5, 0), ("AC ligado", "ac", 5, 1), ("Pre-aquecimento", "pre_aquecimento", 5, 2)
        ]

        for text, key, row, col in checks_config_sls:
            ctk.CTkCheckBox(self.frm_sls_checklist, text=text, font=theme.font_body(11), variable=self.sls_vars[key], **checkbox_kwargs).grid(row=row, column=col, padx=15, pady=6, sticky="w")

        # Botão Guardar
        self.btn_salvar = theme.button_action(frm, text="🚀 INICIAR FABRICO", height=45, font=self.f_titulo, command=self.gravar_producao)

    def ao_selecionar_maquina(self, nome_maquina: str):
        """Verifica recorrência de NC não resolvida na máquina escolhida e
        mostra um aviso inline — não bloqueia, apenas chama a atenção antes
        de lançar mais uma produção sobre um problema conhecido."""
        if not nome_maquina or nome_maquina.startswith(("Sem ", "Erro", "A carregar")):
            self.lbl_alerta_recorrencia.configure(text="")
            return

        id_para_nome = MaquinaService.obter_lookup_id_nome()
        recorrencias = NCService.detectar_recorrencia(nome_maquina, id_para_nome)

        if recorrencias:
            msg = NCService.formatar_alerta_recorrencia(recorrencias)
            self.lbl_alerta_recorrencia.configure(
                text=f"⚠️ Problema recorrente nesta máquina:\n{msg}")
        else:
            self.lbl_alerta_recorrencia.configure(text="")

    def preencher_lote_anterior(self):
        if self.chk_var_lote.get():
            lote = ProducaoService.obter_ultimo_lote_sls()
            if lote:
                self.ent_lote.delete(0, 'end')
                self.ent_lote.insert(0, lote)
            else:
                self.chk_var_lote.set(False)
                messagebox.showinfo("Info", "Nenhum registo de lote de pó anterior encontrado.")
        else:
            self.ent_lote.delete(0, 'end')

    def _atualizar_lista_templates(self, tecnologia: str):
        """Atualiza o combobox de templates para a tecnologia selecionada."""
        templates = TemplateService.obter_por_tecnologia(tecnologia)
        # Ordena por popularidade (mais usados primeiro)
        templates = sorted(templates, key=lambda t: -t.get("uso_count", 0))
        self._templates_cache = {t["nome"]: t for t in templates}
        valores = ["Nenhum"] + list(self._templates_cache.keys())
        self.cmb_template.configure(values=valores)
        self.cmb_template.set("Nenhum")

    def aplicar_template(self, nome_escolhido: str):
        """Pré-preenche o formulário com os valores guardados no template."""
        if nome_escolhido == "Nenhum" or nome_escolhido not in getattr(self, "_templates_cache", {}):
            return
        t = self._templates_cache[nome_escolhido]

        # Máquina — só aplica se ainda estiver na lista de compatíveis
        if t.get("id_maquina") in self.cmb_maq.cget("values"):
            self.cmb_maq.set(t["id_maquina"])

        if t.get("tempo_estimado"):
            self.ent_tempo.delete(0, "end")
            self.ent_tempo.insert(0, t["tempo_estimado"])

        tech = t.get("tecnologia", "")
        if tech == "SLS":
            if t.get("altura_cuba"):
                self.ent_altura.delete(0, "end")
                self.ent_altura.insert(0, t["altura_cuba"])
            if t.get("percentagem_po"):
                self.ent_perc.delete(0, "end")
                self.ent_perc.insert(0, t["percentagem_po"])
        else:
            if t.get("material") and hasattr(self, "ent_quant"):
                pass  # quantidade é sempre específica do job, não vem do template

        TemplateService.registar_uso(t["id"])
        messagebox.showinfo("Template Aplicado",
            f"Parâmetros de \"{nome_escolhido}\" aplicados.\nAjusta a quantidade/tempo se necessário.")

    def abrir_guardar_template(self):
        """Popup simples para nomear e guardar os valores atuais como template."""
        tech_atual = self.cmb_tech.get()
        maq_atual = self.cmb_maq.get()

        if not maq_atual or maq_atual == "A carregar...":
            messagebox.showwarning("Aviso", "Seleciona uma máquina antes de guardar o template.")
            return

        popup = ctk.CTkToplevel(self.parent.winfo_toplevel())
        popup.title("Guardar Template")
        popup.geometry("400x180")
        popup.transient(self.parent.winfo_toplevel())
        popup.grab_set()

        ctk.CTkLabel(popup, text="Nome do Template", font=theme.font_eyebrow(11),
                     text_color=theme.TEXT_MUTED).pack(padx=20, pady=(20, 5), anchor="w")
        ent_nome = theme.entry(popup, font=self.f_padrao, width=340,
                               placeholder_text=f"Ex: {tech_atual} Padrão - {maq_atual}")
        ent_nome.pack(padx=20, pady=(0, 15))

        def _guardar():
            nome = ent_nome.get().strip()
            if not nome:
                messagebox.showwarning("Aviso", "Indica um nome para o template.")
                return
            TemplateService.criar_template(
                nome=nome,
                tecnologia=tech_atual,
                id_maquina=maq_atual,
                tempo_estimado=self.ent_tempo.get().strip(),
                altura_cuba=self.ent_altura.get().strip() if tech_atual == "SLS" else "",
                percentagem_po=self.ent_perc.get().strip() if tech_atual == "SLS" else "",
            )
            self._atualizar_lista_templates(tech_atual)
            popup.destroy()
            messagebox.showinfo("Sucesso", f"Template \"{nome}\" guardado.")

        theme.button_action(popup, text="Guardar", command=_guardar, height=36).pack(
            padx=20, pady=5, fill="x")

    def ao_mudar_tecnologia(self, escolha=None):
        # Usa o valor recebido quando disponível: no arranque, self.cmb_tech ainda não
        # foi ".set()" pelo utilizador, por isso `.get()` devolveria vazio nesse caso.
        tech_atual = escolha or self.cmb_tech.get()
        self.cmb_tech.set(tech_atual)

        # 1. Reset dos pedidos vinculados
        self.pedidos_vinculados = []
        self.ent_pedidos_sel.configure(state="normal")
        self.ent_pedidos_sel.delete(0, "end")
        self.ent_pedidos_sel.insert(0, "Nenhum pedido selecionado")
        self.ent_pedidos_sel.configure(state="readonly")

        # 1.5. Atualiza a lista de templates disponíveis para esta tecnologia
        self._atualizar_lista_templates(tech_atual)

        # 2. Esconde tudo
        self.lbl_quant.grid_forget()
        self.ent_quant.grid_forget()
        self.lbl_altura.grid_forget()
        self.ent_altura.grid_forget()
        self.lbl_perc.grid_forget()
        self.ent_perc.grid_forget()
        self.frm_fdm_checklist.grid_forget()
        self.frm_sla_checklist.grid_forget()
        self.frm_sls_checklist.grid_forget()
        self.btn_salvar.grid_forget()

        # 3. Mostra consoante a tecnologia
        if tech_atual == "FDM":
            self.lbl_quant.grid(row=5, column=0, padx=15, pady=10, sticky="e")
            self.ent_quant.grid(row=5, column=1, padx=15, pady=10, sticky="w")
            self.frm_fdm_checklist.grid(row=6, column=0, columnspan=3, padx=15, pady=10, sticky="ew")
            self.btn_salvar.grid(row=7, column=0, columnspan=3, padx=15, pady=20, sticky="ew")
            
        elif tech_atual == "SLA":
            self.lbl_quant.grid(row=5, column=0, padx=15, pady=10, sticky="e")
            self.ent_quant.grid(row=5, column=1, padx=15, pady=10, sticky="w")
            self.frm_sla_checklist.grid(row=6, column=0, columnspan=3, padx=15, pady=10, sticky="ew")
            self.btn_salvar.grid(row=7, column=0, columnspan=3, padx=15, pady=20, sticky="ew")
            
        elif tech_atual == "SLS":
            self.lbl_altura.grid(row=5, column=0, padx=15, pady=10, sticky="e")
            self.ent_altura.grid(row=5, column=1, padx=15, pady=10, sticky="w")
            self.lbl_perc.grid(row=6, column=0, padx=15, pady=10, sticky="e")
            self.ent_perc.grid(row=6, column=1, padx=15, pady=10, sticky="w")
            self.frm_sls_checklist.grid(row=7, column=0, columnspan=3, padx=15, pady=10, sticky="ew")
            self.btn_salvar.grid(row=8, column=0, columnspan=3, padx=15, pady=20, sticky="ew")

        # 4. Atualiza as máquinas
        self.atualizar_combos()

    def atualizar_combos(self):
        if not hasattr(self, 'cmb_maq'): return

        tech_atual = self.cmb_tech.get()

        try:
            impressoras = MaquinaService.obter_todas()
            maquinas_compativeis = []

            for imp in impressoras:
                if isinstance(imp, dict):
                    t = imp.get("tech", tech_atual)
                    nome = imp.get("nome", "Desconhecida")
                    st = imp.get("estado", "Ativa")
                    
                    st_lower = st.lower()
                    inativa = "inativa" in st_lower or "manutenção" in st_lower or "manutencao" in st_lower
                    if t == tech_atual and not inativa:
                        maquinas_compativeis.append(nome)
                elif isinstance(imp, str):
                    maquinas_compativeis.append(imp)

            if maquinas_compativeis:
                self.cmb_maq.configure(values=maquinas_compativeis)
                self.cmb_maq.set(maquinas_compativeis[0])
                self.ao_selecionar_maquina(maquinas_compativeis[0])
            else:
                self.cmb_maq.configure(values=[f"Sem máquinas p/ {tech_atual}"])
                self.cmb_maq.set(f"Sem p/ {tech_atual}")
                self.lbl_alerta_recorrencia.configure(text="")

        except Exception as e:
            self.cmb_maq.configure(values=["Erro ao ler ficheiro"])
            self.cmb_maq.set("Erro")
            print(f"Erro em atualizar_combos: {e}")

    def abrir_pop_up_selecao_pedidos(self):
        tech_atual = self.cmb_tech.get()
        pedidos_db = PedidoService.obter_todos()
        
        pedidos_compativeis = [
            p for p in pedidos_db 
            if p.get("estado", "") in ["Pendente", "Em Andamento"]
            and p.get("tecnologia") == tech_atual
        ]

        if not pedidos_compativeis:
            messagebox.showinfo("Aviso", f"Não existem pedidos em aberto para a tecnologia {tech_atual}.")
            return

        top = ctk.CTkToplevel(self.parent.winfo_toplevel())
        top.title(f"Selecionar Pedidos ({tech_atual})")
        top.geometry("600x480")
        top.configure(fg_color=theme.BG)
        top.transient(self.parent.winfo_toplevel())
        top.grab_set()

        ctk.CTkLabel(top, text=f"Pedidos Abertos ({tech_atual}):", font=theme.font_body(13, "bold"), text_color=theme.ACCENT).pack(pady=(15, 5))
        ctk.CTkLabel(top, text="Nota: Só é possível agrupar pedidos do mesmo material.", font=theme.font_body(10), text_color=theme.TEXT_MUTED).pack(pady=(0, 10))

        scroll_frame = ctk.CTkScrollableFrame(top, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.dict_checks_pedidos = []
        ids_ja_selecionados = list(self.pedidos_vinculados)

        def extrair_materiais_pedido(p):
            mats = set()
            for peca in p.get("pecas", []):
                if peca.get("material"): mats.add(peca.get("material"))
            return list(mats)

        def reavaliar_bloqueio_materiais():
            mats_ativos = set()
            for item in self.dict_checks_pedidos:
                if item["var"].get(): mats_ativos.update(item["materiais"])

            for item in self.dict_checks_pedidos:
                if not mats_ativos:
                    item["widget"].configure(state="normal", text_color=theme.TEXT)
                else:
                    if any(m in mats_ativos for m in item["materiais"]):
                        item["widget"].configure(state="normal", text_color=theme.TEXT)
                    else:
                        item["var"].set(False)
                        item["widget"].configure(state="disabled", text_color=theme.TEXT_MUTED)

        for p in pedidos_compativeis:
            id_p = p.get("id")
            nr_proj = p.get("nr_projeto", "S/N")
            mats = extrair_materiais_pedido(p)
            mat_str = ", ".join(mats) if mats else "N/A"
            
            label_text = f"{PedidoService.formatar_codigo(id_p)} | Proj: {nr_proj} | Mat: {mat_str}"

            var = tk.BooleanVar(value=(id_p in ids_ja_selecionados))
            chk = ctk.CTkCheckBox(scroll_frame, text=label_text, variable=var, font=theme.font_body(11),
                                   fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, checkmark_color=theme.WHITE,
                                   border_color=theme.TEXT_MUTED, command=reavaliar_bloqueio_materiais)
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
                ids_str = ", ".join(PedidoService.formatar_codigo(item['id']) for item in selecionados)
                self.ent_pedidos_sel.insert(0, f"Pedidos Vinculados: {ids_str}")
                
            self.ent_pedidos_sel.configure(state="readonly")
            top.destroy()

        theme.button_action(top, text="CONFIRMAR SELEÇÃO", font=theme.font_body(12, "bold"), height=40, command=confirmar_selecao).pack(fill="x", padx=20, pady=15)

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
        # 1. VALIDAÇÕES BÁSICAS
        if not self.pedidos_vinculados:
            messagebox.showwarning("Aviso", "Por favor, vincule pelo menos um pedido à produção.")
            return

        tempo = self.ent_tempo.get().strip()
        if not tempo or not ProducaoService.validar_formato_tempo(tempo):
            messagebox.showwarning("Aviso", "Introduza um tempo de máquina válido (HH:MM).")
            return

        tech = self.cmb_tech.get()
        maq = self.cmb_maq.get()

        if maq.startswith("Sem máquinas") or maq == "A carregar..." or maq.startswith("Erro"):
            messagebox.showwarning("Aviso", "Selecione uma máquina válida antes de iniciar o fabrico.")
            return

        # Aviso de qualidade: problema recorrente sem correção confirmada
        # nesta máquina. Não bloqueia — o operador pode decidir prosseguir
        # (ex: causa já identificada mas correção agendada para depois).
        id_para_nome = MaquinaService.obter_lookup_id_nome()
        recorrencias = NCService.detectar_recorrencia(maq, id_para_nome)
        if recorrencias:
            msg = NCService.formatar_alerta_recorrencia(recorrencias)
            if not messagebox.askyesno(
                "Problema Recorrente Detetado",
                f"Esta máquina teve não-conformidades repetidas sem correção confirmada:\n\n{msg}\n\n"
                "Desejas iniciar esta produção mesmo assim?"
            ):
                return

        # ==========================================
        # 2. SAFETY LOCKS (TRAVAS DE SEGURANÇA)
        # ==========================================
        if tech == "FDM":
            quant = self.ent_quant.get().strip()
            if not quant or not ProducaoService.validar_numero_positivo(quant):
                messagebox.showwarning("Aviso", "Bloqueio: A Quantidade de material (g) tem de ser um número válido maior que zero.")
                return

            # Verifica se TODOS os checks estão marcados
            if not all(var.get() for var in self.fdm_vars.values()):
                messagebox.showwarning("Erro de Qualidade", "Bloqueio: É obrigatório validar todos os itens da Checklist Crítica FDM para iniciar a produção.")
                return

        elif tech == "SLA":
            quant = self.ent_quant.get().strip()
            if not quant or not ProducaoService.validar_numero_positivo(quant):
                messagebox.showwarning("Aviso", "Bloqueio: A Quantidade de resina (ml) tem de ser um número válido maior que zero.")
                return

            # Verifica se TODOS os checks estão marcados
            if not all(var.get() for var in self.sla_vars.values()):
                messagebox.showwarning("Erro de Qualidade", "Bloqueio: É obrigatório validar todos os itens da Checklist Crítica SLA para iniciar a produção.")
                return

        elif tech == "SLS":
            altura = self.ent_altura.get().strip()
            perc = self.ent_perc.get().strip()
            lote = self.ent_lote.get().strip()

            if not altura or not perc or not lote:
                messagebox.showwarning("Aviso", "Bloqueio: A Altura da Cuba, % de Pó Novo e Lote do Pó são obrigatórios.")
                return

            if not ProducaoService.validar_numero_positivo(altura) or not ProducaoService.validar_numero_positivo(perc):
                messagebox.showwarning("Aviso", "Bloqueio: A Altura da Cuba e a % de Pó Novo têm de ser números válidos maiores que zero.")
                return

            # Verifica se TODOS os checks estão marcados
            if not all(var.get() for var in self.sls_vars.values()):
                messagebox.showwarning("Erro de Qualidade", "Bloqueio: É obrigatório validar todos os parâmetros e Checklist Crítica SLS para iniciar a produção.")
                return

        # ==========================================
        # 3. GRAVAÇÃO DOS DADOS
        # ==========================================
        responsavel = os.environ.get("USERNAME", "Desconhecido")
        quant = ""  # inicializado aqui para evitar UnboundLocalError se a lógica mudar

        campos_extra = {}
        if tech in ("FDM", "SLA"):
            campos_extra["quantidade_consumida"] = quant
            checklist = self.fdm_vars if tech == "FDM" else self.sla_vars
            campos_extra["checklist_seguranca"] = {k: v.get() for k, v in checklist.items()}
        elif tech == "SLS":
            campos_extra["altura_cuba"] = altura
            campos_extra["percentagem_po_novo"] = perc
            campos_extra["lote_po"] = lote
            campos_extra["checklist_seguranca"] = {k: v.get() for k, v in self.sls_vars.items()}

        # Cria a produção e vincula-a aos pedidos sob os locks atómicos de cada
        # serviço, para evitar tanto IDs duplicados como o link inverso
        # (producoes_vinculadas) ficar por escrever.
        nova_producao = ProducaoService.criar_producao(
            tecnologia=tech,
            maquina=maq,
            tempo_estimado=tempo,
            pedidos_vinculados=self.pedidos_vinculados,
            operador=responsavel,
            campos_extra=campos_extra,
        )
        novo_id = nova_producao["id"]

        PedidoService.vincular_producao(self.pedidos_vinculados, novo_id)

        messagebox.showinfo("Sucesso", f"Produção {ProducaoService.formatar_codigo(novo_id)} iniciada com sucesso na máquina {maq}!\n\nDados guardados em producao_i3D.json.")
        
        self.ao_mudar_tecnologia(tech)
        self.ent_tempo.delete(0, 'end')
        self.ent_quant.delete(0, 'end')
        self.ent_altura.delete(0, 'end')
        self.ent_perc.delete(0, 'end')
        self.ent_lote.delete(0, 'end')
        
        for chk_var in self.fdm_vars.values(): chk_var.set(False)
        for chk_var in self.sla_vars.values(): chk_var.set(False)
        for chk_var in self.sls_vars.values(): chk_var.set(False)
        self.chk_var_lote.set(False)