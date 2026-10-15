"""Nova ordem de produção — formulário à esquerda, resumo dos pedidos
escolhidos à direita, e um rodapé fixo com o botão de iniciar que diz o que
falta preencher (em vez de uma sequência de pop-ups de erro ao clicar)."""
import os
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from services.pedido_service import PedidoService
from services.producao_service import ProducaoService
from services.maquina_service import MaquinaService
from services.template_service import TemplateService
from services.nc_service import NCService
from gui import theme

_UNIDADE = {"FDM": "g", "SLA": "ml"}

_CHECKLIST = {
    "FDM": [("nivelamento_mesa", "Nivelamento da mesa"), ("analise_gcode", "Análise do G-code"),
            ("qualidade_filamento", "Qualidade do filamento")],
    "SLA": [("limpeza_tanque", "Limpeza do tanque"), ("limpeza_mesa", "Limpeza da plataforma"),
            ("qualidade_resina", "Qualidade da resina")],
    "SLS": [("slicefix", "SliceFix OK"), ("po_suficiente", "Quantidade de pó suficiente"),
            ("abastecimento", "Abastecimento de pó ligado"), ("home_pistao", "Homing do pistão"),
            ("home_rolo", "Homing do rolo"), ("z_adicional", "Z adicional no topo"),
            ("chiller", "Chiller ligado"), ("ac", "AC ligado"), ("pre_aquecimento", "Pré-aquecimento")],
}

_SEM_PEDIDOS = "Nenhum pedido selecionado"


class ProducaoTab:
    def __init__(self, parent_frame, f_padrao=None, f_titulo=None, master_app=None):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.master_app = master_app
        self.pedidos_vinculados = []
        self.dict_checks_pedidos = []
        self._templates_cache = {}
        self.parent.configure(fg_color=theme.BG)

        self.construir_layout()
        self.ao_mudar_tecnologia("FDM")

    # ------------------------------------------------------------------ #
    #  LAYOUT                                                              #
    # ------------------------------------------------------------------ #
    def construir_layout(self):
        cab = theme.page_header(self.parent, "Chão de fábrica", "Nova ordem de produção")
        cab.pack(fill="x", padx=24, pady=(18, 8))
        theme.button_ghost(cab.acoes, text="Guardar como template", height=34,
                           command=self.abrir_guardar_template).pack(side="left")

        # Rodapé fixo: o que falta + iniciar (nunca sai do ecrã)
        frm_rodape = theme.card(self.parent)
        frm_rodape.pack(side="bottom", fill="x", padx=24, pady=(0, 16))
        self.lbl_falta = ctk.CTkLabel(frm_rodape, text="", font=theme.font_body(12), text_color=theme.TEXT_MUTED,
                                      anchor="w", justify="left", wraplength=700)
        self.lbl_falta.pack(side="left", fill="x", expand=True, padx=16, pady=12)
        self.btn_salvar = theme.button_action(frm_rodape, text="Iniciar fabrico", height=42, width=200,
                                              font=theme.font_body(15, "bold"), command=self.gravar_producao)
        self.btn_salvar.pack(side="right", padx=16, pady=12)

        corpo = ctk.CTkFrame(self.parent, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=24, pady=(0, 10))
        corpo.columnconfigure(0, weight=3, uniform="col")
        corpo.columnconfigure(1, weight=2, uniform="col")
        corpo.rowconfigure(0, weight=1)

        # ── Coluna esquerda: formulário (com scroll) ─────────────────────
        card_form = theme.card(corpo)
        card_form.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        frm = ctk.CTkScrollableFrame(card_form, fg_color="transparent")
        frm.pack(fill="both", expand=True, padx=4, pady=4)
        frm.columnconfigure(0, weight=1)
        self._frm = frm
        linha = 0

        def _rotulo(texto, obrigatorio=False):
            nonlocal linha
            theme.rotulo_campo(frm, texto, obrigatorio).grid(row=linha, column=0, sticky="w", padx=14, pady=(12, 3))
            linha += 1

        _rotulo("Tecnologia", True)
        self.cmb_tech = theme.segmented(frm, values=["FDM", "SLA", "SLS"], command=self.ao_mudar_tecnologia)
        self.cmb_tech.grid(row=linha, column=0, sticky="w", padx=14)
        linha += 1

        _rotulo("Template (opcional)")
        self.cmb_template = theme.combobox(frm, values=["Nenhum"], width=320, state="readonly", command=self.aplicar_template)
        self.cmb_template.set("Nenhum")
        self.cmb_template.grid(row=linha, column=0, sticky="w", padx=14)
        linha += 1

        _rotulo("Pedidos a produzir", True)
        frm_ped = ctk.CTkFrame(frm, fg_color="transparent")
        frm_ped.grid(row=linha, column=0, sticky="ew", padx=14)
        linha += 1
        self.ent_pedidos_sel = theme.entry(frm_ped)
        self.ent_pedidos_sel.insert(0, _SEM_PEDIDOS)
        self.ent_pedidos_sel.configure(state="readonly")
        self.ent_pedidos_sel.pack(side="left", fill="x", expand=True, padx=(0, 10))
        theme.button_ghost(frm_ped, text="Selecionar pedidos", width=160, command=self.abrir_pop_up_selecao_pedidos).pack(side="right")

        _rotulo("Máquina", True)
        self.cmb_maq = theme.combobox(frm, values=["A carregar..."], width=320, state="readonly", command=self.ao_selecionar_maquina)
        self.cmb_maq.grid(row=linha, column=0, sticky="w", padx=14)
        linha += 1
        # Alerta de NC recorrente — só aparece quando há um problema não
        # resolvido na máquina escolhida.
        self.lbl_alerta_recorrencia = ctk.CTkLabel(frm, text="", font=theme.font_body(12, "bold"), text_color=theme.WARNING,
                                                   justify="left", wraplength=520, anchor="w")
        self.lbl_alerta_recorrencia.grid(row=linha, column=0, sticky="w", padx=14)
        self.lbl_alerta_recorrencia.grid_remove()  # só ocupa espaço quando há aviso
        linha += 1

        frm_num = ctk.CTkFrame(frm, fg_color="transparent")
        frm_num.grid(row=linha, column=0, sticky="ew", padx=14, pady=(8, 0))
        linha += 1
        self._frm_num = frm_num

        def _num(texto, placeholder):
            col = ctk.CTkFrame(frm_num, fg_color="transparent")
            lbl = theme.rotulo_campo(col, texto, True)
            lbl.pack(anchor="w", pady=(4, 3))
            ent = theme.entry(col, placeholder_text=placeholder, font=theme.font_mono(13), width=160)
            ent.pack(anchor="w")
            ent.bind("<KeyRelease>", lambda e: self._atualizar_estado(), add="+")
            return col, lbl, ent

        self._col_tempo, _, self.ent_tempo = _num("Tempo de máquina (HH:MM)", "ex.: 02:30")
        # A máscara reformata "0230" → "02:30"; o estado do rodapé é recalculado depois dela.
        self.ent_tempo.bind("<KeyRelease>", lambda e: (self.mascara_tempo(e, self.ent_tempo), self._atualizar_estado()), add="+")
        self._col_quant, self.lbl_quant, self.ent_quant = _num("Quantidade (g)", "ex.: 150")
        self._col_altura, self.lbl_altura, self.ent_altura = _num("Altura da cuba (mm)", "ex.: 320")
        self._col_perc, self.lbl_perc, self.ent_perc = _num("Pó novo (fração)", "ex.: 0.3")
        self._col_tempo.grid(row=0, column=0, sticky="w", padx=(0, 16), pady=(0, 6))

        # Checklists por tecnologia
        self.checklist_vars = {}
        self.frm_checklists = {}
        for tech, itens in _CHECKLIST.items():
            bloco = ctk.CTkFrame(frm, fg_color=theme.SURFACE_ALT, corner_radius=theme.RADIUS_M, border_width=1, border_color=theme.BORDER)
            self.frm_checklists[tech] = bloco
            cab_chk = ctk.CTkFrame(bloco, fg_color="transparent")
            cab_chk.grid(row=0, column=0, columnspan=3, sticky="ew", padx=14, pady=(10, 4))
            ctk.CTkLabel(cab_chk, text=f"Checklist crítico {tech}", font=theme.font_body(13, "bold"),
                         text_color=theme.TEXT).pack(side="left")
            vars_tech = {}
            inicio = 1
            if tech == "SLS":
                self.chk_var_lote = tk.BooleanVar(value=False)
                theme.checkbox(bloco, text="Mesmo lote de pó da produção anterior", variable=self.chk_var_lote,
                               command=self.preencher_lote_anterior).grid(row=1, column=0, columnspan=3, padx=14, pady=(4, 6), sticky="w")
                theme.rotulo_campo(bloco, "Lote do pó", True).grid(row=2, column=0, padx=14, sticky="w")
                self.ent_lote = theme.entry(bloco, width=200, font=theme.font_mono(12))
                self.ent_lote.grid(row=3, column=0, columnspan=2, padx=14, pady=(0, 6), sticky="w")
                self.ent_lote.bind("<KeyRelease>", lambda e: self._atualizar_estado(), add="+")
                inicio = 4
            for i, (chave, texto) in enumerate(itens):
                var = tk.BooleanVar(value=False)
                theme.checkbox(bloco, text=texto, variable=var, command=self._atualizar_estado).grid(
                    row=inicio + i // 3, column=i % 3, padx=14, pady=6, sticky="w")
                vars_tech[chave] = var
            self.checklist_vars[tech] = vars_tech
            ctk.CTkLabel(bloco, text="", height=4).grid(row=99, column=0)
        self._linha_checklist = linha
        # Nomes antigos, usados nos testes e na gravação
        self.fdm_vars = self.checklist_vars["FDM"]
        self.sla_vars = self.checklist_vars["SLA"]
        self.sls_vars = self.checklist_vars["SLS"]

        # ── Coluna direita: resumo dos pedidos escolhidos ────────────────
        card_resumo = theme.card(corpo)
        card_resumo.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(card_resumo, text="PEDIDOS NESTA ORDEM", font=theme.font_eyebrow(11), text_color=theme.TEXT_MUTED,
                     anchor="w").pack(fill="x", padx=16, pady=(12, 4))
        self.frm_resumo = ctk.CTkScrollableFrame(card_resumo, fg_color="transparent")
        self.frm_resumo.pack(fill="both", expand=True, padx=6, pady=(0, 10))

    # ------------------------------------------------------------------ #
    #  TECNOLOGIA / MÁQUINA / TEMPLATE                                     #
    # ------------------------------------------------------------------ #
    def ao_mudar_tecnologia(self, escolha=None):
        tech_atual = escolha or self.cmb_tech.get() or "FDM"
        self.cmb_tech.set(tech_atual)

        # Pedidos de outra tecnologia deixam de fazer sentido
        self._definir_pedidos([])
        self._atualizar_lista_templates(tech_atual)

        for col in (self._col_quant, self._col_altura, self._col_perc):
            col.grid_forget()
        for bloco in self.frm_checklists.values():
            bloco.grid_forget()

        if tech_atual in ("FDM", "SLA"):
            self.lbl_quant.configure(text=f"QUANTIDADE ({_UNIDADE[tech_atual].upper()}) *")
            self._col_quant.grid(row=0, column=1, sticky="w", pady=(0, 6))
        else:
            # Em grelha de 2 colunas: 3 campos lado a lado não cabiam num portátil
            self._col_altura.grid(row=0, column=1, sticky="w", pady=(0, 6))
            self._col_perc.grid(row=1, column=0, sticky="w", padx=(0, 16), pady=(0, 6))
        self.frm_checklists[tech_atual].grid(row=self._linha_checklist, column=0, sticky="ew", padx=14, pady=(14, 10))

        self.atualizar_combos()

    def preselecionar(self, tecnologia=None, maquina=None):
        """Usado pelo botão "Iniciar ordem" dos cartões de Máquinas."""
        if tecnologia and tecnologia != self.cmb_tech.get():
            self.ao_mudar_tecnologia(tecnologia)
        if maquina and maquina in self.cmb_maq.cget("values"):
            self.cmb_maq.set(maquina)
            self.ao_selecionar_maquina(maquina)
        self._atualizar_estado()

    def atualizar_combos(self):
        """(Re)carrega as máquinas disponíveis para a tecnologia atual, mantendo
        a escolhida se continuar válida (é chamada sempre que se volta ao ecrã)."""
        tech_atual = self.cmb_tech.get()
        anterior = self.cmb_maq.get()
        try:
            compativeis = []
            for imp in MaquinaService.obter_todas():
                if isinstance(imp, dict):
                    if imp.get("tech", tech_atual) == tech_atual and MaquinaService.esta_disponivel(imp):
                        compativeis.append(imp.get("nome", "Desconhecida"))
                elif isinstance(imp, str):
                    compativeis.append(imp)
            if compativeis:
                self.cmb_maq.configure(values=compativeis)
                escolhida = anterior if anterior in compativeis else compativeis[0]
                self.cmb_maq.set(escolhida)
                self.ao_selecionar_maquina(escolhida)
            else:
                self.cmb_maq.configure(values=[f"Sem máquinas {tech_atual} disponíveis"])
                self.cmb_maq.set(f"Sem máquinas {tech_atual} disponíveis")
                self.lbl_alerta_recorrencia.configure(text="")
        except Exception as e:
            self.cmb_maq.configure(values=["Erro ao ler as máquinas"])
            self.cmb_maq.set("Erro ao ler as máquinas")
            print(f"Erro em atualizar_combos: {e}")
        self._atualizar_estado()

    def _maquina_valida(self):
        maq = self.cmb_maq.get()
        return bool(maq) and not maq.startswith(("Sem máquinas", "Erro", "A carregar"))

    def ao_selecionar_maquina(self, nome_maquina: str):
        """Aviso inline (não bloqueia) se a máquina tem uma NC recorrente sem
        correção confirmada."""
        if not nome_maquina or nome_maquina.startswith(("Sem máquinas", "Erro", "A carregar")):
            self.lbl_alerta_recorrencia.configure(text="")
            return
        recorrencias = NCService.detectar_recorrencia(nome_maquina, MaquinaService.obter_lookup_id_nome())
        if recorrencias:
            self.lbl_alerta_recorrencia.configure(
                text=f"Problema recorrente nesta máquina: {NCService.formatar_alerta_recorrencia(recorrencias)}")
            self.lbl_alerta_recorrencia.grid()
        else:
            self.lbl_alerta_recorrencia.configure(text="")
            self.lbl_alerta_recorrencia.grid_remove()
        self._atualizar_estado()

    def _atualizar_lista_templates(self, tecnologia: str):
        templates = sorted(TemplateService.obter_por_tecnologia(tecnologia), key=lambda t: -t.get("uso_count", 0))
        self._templates_cache = {t["nome"]: t for t in templates}
        self.cmb_template.configure(values=["Nenhum"] + list(self._templates_cache.keys()))
        self.cmb_template.set("Nenhum")

    def aplicar_template(self, nome_escolhido: str):
        """Pré-preenche o formulário com os valores guardados no template."""
        t = self._templates_cache.get(nome_escolhido)
        if not t:
            return
        if t.get("id_maquina") in self.cmb_maq.cget("values"):
            self.cmb_maq.set(t["id_maquina"])
            self.ao_selecionar_maquina(t["id_maquina"])
        if t.get("tempo_estimado"):
            self.ent_tempo.delete(0, "end")
            self.ent_tempo.insert(0, t["tempo_estimado"])
        if t.get("tecnologia") == "SLS":
            if t.get("altura_cuba"):
                self.ent_altura.delete(0, "end")
                self.ent_altura.insert(0, t["altura_cuba"])
            if t.get("percentagem_po"):
                self.ent_perc.delete(0, "end")
                self.ent_perc.insert(0, t["percentagem_po"])
        TemplateService.registar_uso(t["id"])
        theme.toast(self.parent, f"Template \"{nome_escolhido}\" aplicado — confirme tempo e quantidade.", "info")
        self._atualizar_estado()

    def abrir_guardar_template(self):
        if not self._maquina_valida():
            messagebox.showwarning("Sem máquina", "Escolha uma máquina antes de guardar o template.")
            return
        JanelaGuardarTemplate(self.parent.winfo_toplevel(), self)

    # ------------------------------------------------------------------ #
    #  PEDIDOS                                                             #
    # ------------------------------------------------------------------ #
    def _definir_pedidos(self, ids):
        self.pedidos_vinculados = list(ids)
        self.ent_pedidos_sel.configure(state="normal")
        self.ent_pedidos_sel.delete(0, "end")
        if ids:
            self.ent_pedidos_sel.insert(0, "Pedidos: " + ", ".join(PedidoService.formatar_codigo(i) for i in ids))
        else:
            self.ent_pedidos_sel.insert(0, _SEM_PEDIDOS)
        self.ent_pedidos_sel.configure(state="readonly")
        self._atualizar_resumo()
        self._atualizar_estado()

    def _atualizar_resumo(self):
        for w in self.frm_resumo.winfo_children():
            w.destroy()
        pedidos = [p for p in PedidoService.obter_todos() if p.get("id") in self.pedidos_vinculados]
        if not pedidos:
            ctk.CTkLabel(self.frm_resumo, text="Ainda sem pedidos. Use \"Selecionar pedidos\" — só aparecem pedidos "
                                               "abertos da tecnologia escolhida.",
                         font=theme.font_body(12), text_color=theme.TEXT_MUTED, wraplength=240, justify="left",
                         anchor="w").pack(fill="x", padx=10, pady=6)
            return
        for p in pedidos:
            bloco = ctk.CTkFrame(self.frm_resumo, fg_color=theme.SURFACE_ALT, corner_radius=theme.RADIUS_S)
            bloco.pack(fill="x", padx=6, pady=4)
            dias = PedidoService.dias_ate_prazo(p)
            prazo = p.get("data_entrega", "—")
            cor_prazo = theme.CRITICAL if dias is not None and dias < 0 else (theme.WARNING if dias is not None and dias <= 2 else theme.TEXT_MUTED)
            topo = ctk.CTkFrame(bloco, fg_color="transparent")
            topo.pack(fill="x", padx=10, pady=(8, 0))
            ctk.CTkLabel(topo, text=PedidoService.formatar_codigo(p.get("id")), font=theme.font_mono(12, "bold"),
                         text_color=theme.TEXT).pack(side="left")
            ctk.CTkLabel(topo, text=f"prazo {prazo}", font=theme.font_body(11), text_color=cor_prazo).pack(side="right")
            projeto = f"{p.get('nr_projeto', '')} - {p.get('nome_projeto', '')}".strip(" -")
            ctk.CTkLabel(bloco, text=projeto, font=theme.font_body(12), text_color=theme.TEXT, anchor="w",
                         wraplength=240, justify="left").pack(fill="x", padx=10)
            for peca in p.get("pecas", []):
                ctk.CTkLabel(bloco, text=f"•  {peca.get('pn', '')}  ×{peca.get('qtd_solicitada', '')}  ({peca.get('material', '')})",
                             font=theme.font_body(11), text_color=theme.TEXT_MUTED, anchor="w", wraplength=240,
                             justify="left").pack(fill="x", padx=10)
            ctk.CTkLabel(bloco, text="", height=4).pack()

    def abrir_pop_up_selecao_pedidos(self):
        tech_atual = self.cmb_tech.get()
        compativeis = [p for p in PedidoService.obter_todos()
                       if p.get("estado", "") in PedidoService.ESTADOS_ABERTOS and p.get("ativo") is not False
                       and p.get("tecnologia") == tech_atual]
        if not compativeis:
            messagebox.showinfo("Sem pedidos abertos", f"Não existem pedidos em aberto para {tech_atual}.")
            return
        self.dialogo_selecao = JanelaSelecionarPedidos(self.parent.winfo_toplevel(), self, compativeis)

    # ------------------------------------------------------------------ #
    #  VALIDAÇÃO / GRAVAÇÃO                                                #
    # ------------------------------------------------------------------ #
    def mascara_tempo(self, event, entry):
        val = entry.get().replace(":", "")
        if not val.isdigit():
            entry.delete(0, tk.END)
            return
        if len(val) > 4:
            val = val[:4]
        if len(val) >= 3:
            entry.delete(0, tk.END)
            entry.insert(0, f"{val[:2]}:{val[2:]}")

    def preencher_lote_anterior(self):
        if self.chk_var_lote.get():
            lote = ProducaoService.obter_ultimo_lote_sls()
            if lote:
                self.ent_lote.delete(0, "end")
                self.ent_lote.insert(0, lote)
            else:
                self.chk_var_lote.set(False)
                messagebox.showinfo("Sem lote anterior", "Não há nenhum lote de pó registado numa produção anterior.")
        else:
            self.ent_lote.delete(0, "end")
        self._atualizar_estado()

    def _em_falta(self):
        """Lista do que falta para poder iniciar (mostrada no rodapé)."""
        tech = self.cmb_tech.get()
        falta = []
        if not self.pedidos_vinculados:
            falta.append("pedidos")
        if not self._maquina_valida():
            falta.append("máquina")
        if not ProducaoService.validar_formato_tempo(self.ent_tempo.get()):
            falta.append("tempo")
        if tech in ("FDM", "SLA") and not ProducaoService.validar_numero_positivo(self.ent_quant.get()):
            falta.append("quantidade")
        if tech == "SLS":
            if not ProducaoService.validar_numero_positivo(self.ent_altura.get()):
                falta.append("altura da cuba")
            if not ProducaoService.validar_numero_positivo(self.ent_perc.get()):
                falta.append("% de pó novo")
            if not self.ent_lote.get().strip():
                falta.append("lote do pó")
        vars_tech = self.checklist_vars.get(tech, {})
        feitos = sum(1 for v in vars_tech.values() if v.get())
        if feitos < len(vars_tech):
            falta.append(f"checklist ({feitos}/{len(vars_tech)})")
        return falta

    def _atualizar_estado(self):
        if not hasattr(self, "lbl_falta"):
            return
        falta = self._em_falta()
        if falta:
            self.lbl_falta.configure(text="Falta preencher: " + ", ".join(falta), text_color=theme.TEXT_MUTED)
            theme.definir_ativo(self.btn_salvar, False)
        else:
            self.lbl_falta.configure(text="Tudo verificado — pronto a iniciar.", text_color=theme.SUCCESS)
            theme.definir_ativo(self.btn_salvar, True)

    def gravar_producao(self):
        # As mesmas regras do rodapé, com a mensagem específica de cada bloqueio.
        if not self.pedidos_vinculados:
            messagebox.showwarning("Sem pedidos", "Vincule pelo menos um pedido a esta ordem.")
            return
        tempo = self.ent_tempo.get().strip()
        if not tempo or not ProducaoService.validar_formato_tempo(tempo):
            messagebox.showwarning("Tempo inválido", "Indique o tempo de máquina no formato HH:MM (ex: 02:30).")
            return
        tech = self.cmb_tech.get()
        maq = self.cmb_maq.get()
        if not self._maquina_valida():
            messagebox.showwarning("Sem máquina", "Escolha uma máquina disponível antes de iniciar o fabrico.")
            return

        # Aviso de qualidade: NC recorrente sem correção confirmada nesta máquina.
        # Não bloqueia — a correção pode já estar identificada e agendada.
        recorrencias = NCService.detectar_recorrencia(maq, MaquinaService.obter_lookup_id_nome())
        if recorrencias:
            msg = NCService.formatar_alerta_recorrencia(recorrencias)
            if not messagebox.askyesno("Problema recorrente",
                                       f"Esta máquina teve não-conformidades repetidas sem correção confirmada:\n\n{msg}\n\n"
                                       "Iniciar esta ordem mesmo assim?"):
                return

        # Travas de segurança por tecnologia
        campos_extra = {}
        if tech in ("FDM", "SLA"):
            quant = self.ent_quant.get().strip()
            if not quant or not ProducaoService.validar_numero_positivo(quant):
                messagebox.showwarning("Quantidade inválida", f"A quantidade ({_UNIDADE[tech]}) tem de ser um número maior que zero.")
                return
            if not all(var.get() for var in self.checklist_vars[tech].values()):
                messagebox.showwarning("Checklist incompleto", f"Valide todos os itens do checklist crítico {tech} antes de iniciar.")
                return
            campos_extra["quantidade_consumida"] = quant
            campos_extra["checklist_seguranca"] = {k: v.get() for k, v in self.checklist_vars[tech].items()}
        elif tech == "SLS":
            altura, perc, lote = self.ent_altura.get().strip(), self.ent_perc.get().strip(), self.ent_lote.get().strip()
            if not altura or not perc or not lote:
                messagebox.showwarning("Dados SLS em falta", "Altura da cuba, % de pó novo e lote do pó são obrigatórios.")
                return
            if not ProducaoService.validar_numero_positivo(altura) or not ProducaoService.validar_numero_positivo(perc):
                messagebox.showwarning("Dados SLS inválidos", "Altura da cuba e % de pó novo têm de ser números maiores que zero.")
                return
            if not all(var.get() for var in self.sls_vars.values()):
                messagebox.showwarning("Checklist incompleto", "Valide todos os itens do checklist crítico SLS antes de iniciar.")
                return
            campos_extra.update({"altura_cuba": altura, "percentagem_po_novo": perc, "lote_po": lote,
                                 "checklist_seguranca": {k: v.get() for k, v in self.sls_vars.items()}})

        # Cria a produção e vincula-a aos pedidos sob os locks de cada serviço,
        # para evitar IDs duplicados e o link inverso por escrever.
        nova_producao = ProducaoService.criar_producao(
            tecnologia=tech, maquina=maq, tempo_estimado=tempo,
            pedidos_vinculados=self.pedidos_vinculados,
            operador=os.environ.get("USERNAME", "Desconhecido"),
            campos_extra=campos_extra,
        )
        PedidoService.vincular_producao(self.pedidos_vinculados, nova_producao["id"])
        theme.toast(self.parent, f"Ordem {ProducaoService.formatar_codigo(nova_producao['id'])} iniciada em {maq}.")

        # Limpa o formulário para a próxima ordem
        for ent in (self.ent_tempo, self.ent_quant, self.ent_altura, self.ent_perc, self.ent_lote):
            ent.delete(0, "end")
        for vars_tech in self.checklist_vars.values():
            for v in vars_tech.values():
                v.set(False)
        self.chk_var_lote.set(False)
        self.ao_mudar_tecnologia(tech)


class JanelaSelecionarPedidos(theme.Dialogo):
    """Escolha dos pedidos a produzir numa ordem. Só se agrupam pedidos com o
    mesmo material — os incompatíveis ficam desativados com o motivo à vista."""

    def __init__(self, parent, tab, pedidos):
        self.tab = tab
        super().__init__(parent, f"Selecionar pedidos ({tab.cmb_tech.get()})", largura=640, altura=520,
                         texto_acao="Confirmar seleção", estilo_acao="action",
                         subtitulo="Só é possível agrupar pedidos do mesmo material.")
        tab.dict_checks_pedidos = []
        ja_selecionados = set(tab.pedidos_vinculados)
        for p in pedidos:
            mats = sorted({peca.get("material") for peca in p.get("pecas", []) if peca.get("material")})
            n_pecas = sum(int(peca.get("qtd_solicitada", 0) or 0) for peca in p.get("pecas", []))
            linha = ctk.CTkFrame(self.corpo, fg_color="transparent")
            linha.pack(fill="x", padx=8, pady=4)
            var = tk.BooleanVar(value=p.get("id") in ja_selecionados)
            texto = (f"{PedidoService.formatar_codigo(p.get('id'))}  ·  {p.get('nr_projeto', '')} {p.get('nome_projeto', '')}  ·  "
                     f"{', '.join(mats) or 'sem material'}  ·  {n_pecas} un.  ·  prazo {p.get('data_entrega', '—')}")
            chk = theme.checkbox(linha, text=texto, variable=var, command=self.reavaliar_bloqueio_materiais)
            chk.pack(side="left", anchor="w")
            lbl_motivo = ctk.CTkLabel(linha, text="", font=theme.font_body(11), text_color=theme.TEXT_MUTED)
            lbl_motivo.pack(side="left", padx=8)
            tab.dict_checks_pedidos.append({"id": p.get("id"), "var": var, "widget": chk, "materiais": mats,
                                            "objeto": p, "motivo": lbl_motivo})
        self.reavaliar_bloqueio_materiais()

    def reavaliar_bloqueio_materiais(self):
        itens = self.tab.dict_checks_pedidos
        ativos = set()
        for item in itens:
            if item["var"].get():
                ativos.update(item["materiais"])
        for item in itens:
            compativel = not ativos or any(m in ativos for m in item["materiais"])
            if compativel:
                item["widget"].configure(state="normal", text_color=theme.TEXT)
                item["motivo"].configure(text="")
            else:
                item["var"].set(False)
                item["widget"].configure(state="disabled", text_color=theme.TEXT_MUTED)
                item["motivo"].configure(text="(material diferente)")

    def confirmar(self):
        self.tab._definir_pedidos([item["id"] for item in self.tab.dict_checks_pedidos if item["var"].get()])
        self.destroy()


class JanelaGuardarTemplate(theme.Dialogo):
    def __init__(self, parent, tab):
        self.tab = tab
        tech, maq = tab.cmb_tech.get(), tab.cmb_maq.get()
        super().__init__(parent, "Guardar como template", largura=460, altura=280, scroll=False,
                         subtitulo="Guarda a tecnologia, a máquina, o tempo e (SLS) os parâmetros da cuba.")
        theme.rotulo_campo(self.corpo, "Nome do template", True).pack(anchor="w", pady=(8, 2))
        self.ent_nome = theme.entry(self.corpo, placeholder_text=f"ex.: {tech} padrão - {maq}")
        self.ent_nome.pack(fill="x")
        self.ent_nome.focus_set()

    def confirmar(self):
        nome = self.ent_nome.get().strip()
        if not nome:
            messagebox.showwarning("Nome em falta", "Indique um nome para o template.")
            return
        tab = self.tab
        tech = tab.cmb_tech.get()
        TemplateService.criar_template(
            nome=nome, tecnologia=tech, id_maquina=tab.cmb_maq.get(),
            tempo_estimado=tab.ent_tempo.get().strip(),
            altura_cuba=tab.ent_altura.get().strip() if tech == "SLS" else "",
            percentagem_po=tab.ent_perc.get().strip() if tech == "SLS" else "",
        )
        tab._atualizar_lista_templates(tech)
        theme.toast(self, f"Template \"{nome}\" guardado.")
        self.destroy()
