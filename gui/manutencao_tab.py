import os
import customtkinter as ctk
from tkinter import ttk, messagebox
from services.manutencao_service import ManutencaoService
from services.maquina_service import MaquinaService
from gui import theme

_VARIANTE_ESTADO = {"atrasada": "bad", "proxima": "warn", "ok": "ok", "sem_dados": "neutral"}
_LABEL_ESTADO = {"atrasada": "Atrasada", "proxima": "Próxima", "ok": "OK", "sem_dados": "Sem Dados"}


class ManutencaoTab:
    def __init__(self, parent_frame, f_padrao, f_titulo, master_app=None):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.f_titulo = f_titulo
        self.master_app = master_app

        self.parent.configure(fg_color=theme.BG)

        self.construir_layout()
        self.atualizar_agenda()
        self.atualizar_lista_tarefas()
        self.atualizar_historico()

    def construir_layout(self):
        theme.page_header(self.parent, "Manutenção Preventiva", "Manutenção").pack(fill="x", padx=24, pady=(22, 10))

        self.tabview = ctk.CTkTabview(
            self.parent, fg_color=theme.SURFACE, segmented_button_fg_color=theme.SURFACE_ALT,
            segmented_button_selected_color=theme.ACCENT, segmented_button_selected_hover_color=theme.ACCENT_HOVER,
            text_color=theme.TEXT,
        )
        self.tabview.pack(fill="both", expand=True, padx=24, pady=(0, 18))
        self.tab_agenda = self.tabview.add("Agenda")
        self.tab_tarefas = self.tabview.add("Tarefas Periódicas")
        self.tab_historico = self.tabview.add("Histórico")

        self._estilo_treeview()
        self.construir_tab_agenda()
        self.construir_tab_tarefas()
        self.construir_tab_historico()

    def _estilo_treeview(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Manutencao.Treeview", background=theme.SURFACE[0], foreground=theme.TEXT[0], rowheight=28, fieldbackground=theme.SURFACE[0], borderwidth=0)
        style.configure("Manutencao.Treeview.Heading", background=theme.SURFACE_ALT[0], foreground=theme.TEXT_MUTED[0], borderwidth=0)
        style.map("Manutencao.Treeview", background=[("selected", theme.ACCENT[0])], foreground=[("selected", "white")])

    # ==========================================
    # AGENDA
    # ==========================================
    def construir_tab_agenda(self):
        cols = ("maquina", "modelo", "tarefa", "dias", "horas", "estado")
        anchors = {"maquina": "w", "modelo": "w", "tarefa": "w", "dias": "center", "horas": "center", "estado": "w"}
        self.tree_agenda = ttk.Treeview(self.tab_agenda, columns=cols, show="headings", height=14, style="Manutencao.Treeview")
        for c, h, w in [("maquina", "MÁQUINA", 130), ("modelo", "MODELO", 160), ("tarefa", "TAREFA", 220), ("dias", "DIAS", 70), ("horas", "HORAS", 70), ("estado", "ESTADO", 110)]:
            self.tree_agenda.heading(c, text=h, anchor=anchors[c])
            self.tree_agenda.column(c, width=w, anchor=anchors[c])
        self.tree_agenda.pack(fill="both", expand=True, pady=(10, 5))
        self.agenda_pills = theme.TreeviewPillColumn(self.tree_agenda, "estado")

        frm_acoes = ctk.CTkFrame(self.tab_agenda, fg_color="transparent")
        frm_acoes.pack(fill="x", pady=(0, 10))
        theme.button_action(frm_acoes, text="Marcar como Concluída", command=self.marcar_concluida).pack(side="left")

    def atualizar_agenda(self):
        for i in self.tree_agenda.get_children():
            self.tree_agenda.delete(i)

        linhas = ManutencaoService.calcular_proximas_tarefas()
        self._linhas_agenda = {}
        pill_dados = {}

        for l in linhas:
            dias_txt = str(l["dias_desde"]) if l["dias_desde"] is not None else "-"
            horas_txt = f"{l['horas_desde']:.1f}" if l["horas_desde"] is not None else "-"
            estado_txt = _LABEL_ESTADO[l["estado"]]

            item_id = self.tree_agenda.insert("", "end", values=(
                l["maquina_nome"], l["modelo"], l["tarefa_nome"], dias_txt, horas_txt, estado_txt
            ))
            pill_dados[item_id] = (estado_txt, _VARIANTE_ESTADO[l["estado"]])
            self._linhas_agenda[item_id] = l

        self.agenda_pills.definir_dados(pill_dados)

    def marcar_concluida(self):
        sel = self.tree_agenda.selection()
        if not sel:
            return
        linha = self._linhas_agenda.get(sel[0])
        if not linha:
            return

        operador = os.environ.get("USERNAME", "Desconhecido")
        ManutencaoService.registar_conclusao(linha["tarefa_id"], linha["maquina_id"], operador)

        self.atualizar_agenda()
        self.atualizar_historico()
        # O Dashboard não se auto-atualiza ao mudar de separador — sem isto o badge
        # de alertas ficava desatualizado até à próxima reconstrução do ecrã.
        if self.master_app is not None and hasattr(self.master_app, "historico_ui"):
            self.master_app.historico_ui.atualizar_alertas_manutencao()

        messagebox.showinfo("Registado", "Manutenção registada com sucesso.")

    # ==========================================
    # TAREFAS PERIÓDICAS
    # ==========================================
    def _modelos_disponiveis(self):
        modelos = sorted({m.get("modelo") for m in MaquinaService.obter_todas() if m.get("modelo")})
        return modelos if modelos else ["Sem modelos cadastrados"]

    def construir_tab_tarefas(self):
        frm_form = ctk.CTkFrame(self.tab_tarefas, fg_color="transparent")
        frm_form.pack(fill="x", pady=(10, 5))

        self.cmb_tarefa_modelo = theme.combobox(frm_form, values=self._modelos_disponiveis(), width=170, state="readonly")
        self.cmb_tarefa_modelo.pack(side="left", padx=(0, 10))
        self.ent_tarefa_nome = theme.entry(frm_form, placeholder_text="Nome da Tarefa", width=190)
        self.ent_tarefa_nome.pack(side="left", padx=(0, 10))
        self.ent_tarefa_freq_dias = theme.entry(frm_form, placeholder_text="Dias", width=70, font=theme.font_mono(12))
        self.ent_tarefa_freq_dias.pack(side="left", padx=(0, 10))
        self.ent_tarefa_freq_horas = theme.entry(frm_form, placeholder_text="Horas", width=70, font=theme.font_mono(12))
        self.ent_tarefa_freq_horas.pack(side="left", padx=(0, 10))
        theme.button_action(frm_form, text="Adicionar", command=self.adicionar_tarefa, width=100).pack(side="left")

        cols = ("modelo", "nome", "freq_dias", "freq_horas", "estado")
        anchors = {"modelo": "w", "nome": "w", "freq_dias": "center", "freq_horas": "center", "estado": "w"}
        self.tree_tarefas = ttk.Treeview(self.tab_tarefas, columns=cols, show="headings", height=12, style="Manutencao.Treeview")
        for c, h, w in [("modelo", "MODELO", 160), ("nome", "TAREFA", 220), ("freq_dias", "DIAS", 70), ("freq_horas", "HORAS", 70), ("estado", "ESTADO", 100)]:
            self.tree_tarefas.heading(c, text=h, anchor=anchors[c])
            self.tree_tarefas.column(c, width=w, anchor=anchors[c])
        self.tree_tarefas.pack(fill="both", expand=True, pady=10)
        self.tree_tarefas.bind("<Double-1>", self.editar_tarefa_selecionada)
        self.tarefas_pills = theme.TreeviewPillColumn(self.tree_tarefas, "estado")

        frm_acoes = ctk.CTkFrame(self.tab_tarefas, fg_color="transparent")
        frm_acoes.pack(fill="x", pady=(0, 10))
        theme.button_ghost(frm_acoes, text="Editar Selecionada", command=self.editar_tarefa_selecionada).pack(side="left", padx=(0, 10))
        theme.button_danger(frm_acoes, text="Ativar / Desativar", command=self.toggle_ativa_tarefa).pack(side="left")

    def atualizar_lista_tarefas(self):
        for i in self.tree_tarefas.get_children():
            self.tree_tarefas.delete(i)

        pill_dados = {}
        for t in ManutencaoService.obter_tarefas(incluir_inativas=True):
            estado = "Ativa" if t.get("ativo", True) else "Inativa"
            item_id = self.tree_tarefas.insert("", "end", values=(
                t["modelo"], t["nome"], t.get("frequencia_dias") or "-", t.get("frequencia_horas") or "-", estado,
            ))
            pill_dados[item_id] = (estado, "ok" if estado == "Ativa" else "neutral")
        self.tarefas_pills.definir_dados(pill_dados)

        if hasattr(self, "cmb_tarefa_modelo"):
            self.cmb_tarefa_modelo.configure(values=self._modelos_disponiveis())

    def _ler_frequencias(self, dias_str, horas_str):
        """Devolve (frequencia_dias, frequencia_horas) já convertidos, ou levanta
        ValueError com uma mensagem pronta a mostrar se algum dos campos preenchidos
        não for um número válido."""
        freq_dias = None
        freq_horas = None
        if dias_str:
            try:
                freq_dias = int(dias_str)
            except ValueError:
                raise ValueError("A frequência em dias tem de ser um número inteiro.")
        if horas_str:
            try:
                freq_horas = float(horas_str.replace(",", "."))
            except ValueError:
                raise ValueError("A frequência em horas tem de ser um número válido.")
        return freq_dias, freq_horas

    def adicionar_tarefa(self):
        modelo = self.cmb_tarefa_modelo.get()
        nome = self.ent_tarefa_nome.get().strip()

        if not modelo or modelo == "Sem modelos cadastrados" or not nome:
            messagebox.showwarning("Aviso", "Escolha o Modelo e preencha o Nome da tarefa.")
            return

        try:
            freq_dias, freq_horas = self._ler_frequencias(self.ent_tarefa_freq_dias.get().strip(), self.ent_tarefa_freq_horas.get().strip())
        except ValueError as e:
            messagebox.showwarning("Aviso", str(e))
            return

        try:
            ManutencaoService.criar_tarefa(modelo=modelo, nome=nome, frequencia_dias=freq_dias, frequencia_horas=freq_horas)
        except ValueError as e:
            messagebox.showerror("Erro", str(e))
            return

        self.ent_tarefa_nome.delete(0, "end")
        self.ent_tarefa_freq_dias.delete(0, "end")
        self.ent_tarefa_freq_horas.delete(0, "end")
        self.atualizar_lista_tarefas()
        self.atualizar_agenda()

    def editar_tarefa_selecionada(self, event=None):
        sel = self.tree_tarefas.selection()
        if not sel:
            return
        tarefas = {t["id"]: t for t in ManutencaoService.obter_tarefas(incluir_inativas=True)}
        idx = self.tree_tarefas.index(sel[0])
        tarefa_atual = ManutencaoService.obter_tarefas(incluir_inativas=True)[idx]

        top = ctk.CTkToplevel(self.parent.winfo_toplevel())
        top.title(f"Editar Tarefa - {tarefa_atual['nome']}")
        top.geometry("360x320")
        top.configure(fg_color=theme.BG)
        top.transient(self.parent.winfo_toplevel())
        top.grab_set()

        ctk.CTkLabel(top, text="MODELO", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).pack(pady=(15, 0))
        cmb_modelo = theme.combobox(top, values=self._modelos_disponiveis(), width=260, state="readonly")
        cmb_modelo.set(tarefa_atual["modelo"])
        cmb_modelo.pack(pady=5)

        ctk.CTkLabel(top, text="NOME", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).pack()
        ent_nome = theme.entry(top, width=260)
        ent_nome.insert(0, tarefa_atual["nome"])
        ent_nome.pack(pady=5)

        ctk.CTkLabel(top, text="FREQUÊNCIA (DIAS)", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).pack()
        ent_dias = theme.entry(top, width=260, font=theme.font_mono(12))
        if tarefa_atual.get("frequencia_dias"): ent_dias.insert(0, str(tarefa_atual["frequencia_dias"]))
        ent_dias.pack(pady=5)

        ctk.CTkLabel(top, text="FREQUÊNCIA (HORAS DE USO)", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).pack()
        ent_horas = theme.entry(top, width=260, font=theme.font_mono(12))
        if tarefa_atual.get("frequencia_horas"): ent_horas.insert(0, str(tarefa_atual["frequencia_horas"]))
        ent_horas.pack(pady=5)

        def guardar():
            novo_nome = ent_nome.get().strip()
            if not cmb_modelo.get() or not novo_nome:
                messagebox.showwarning("Aviso", "Preencha o Modelo e o Nome.")
                return
            try:
                freq_dias, freq_horas = self._ler_frequencias(ent_dias.get().strip(), ent_horas.get().strip())
            except ValueError as e:
                messagebox.showwarning("Aviso", str(e))
                return
            try:
                ManutencaoService.atualizar_tarefa({
                    **tarefa_atual, "modelo": cmb_modelo.get(), "nome": novo_nome,
                    "frequencia_dias": freq_dias, "frequencia_horas": freq_horas,
                })
            except ValueError as e:
                messagebox.showerror("Erro", str(e))
                return
            top.destroy()
            self.atualizar_lista_tarefas()
            self.atualizar_agenda()

        theme.button_primary(top, text="Guardar", command=guardar).pack(pady=15)

    def toggle_ativa_tarefa(self):
        sel = self.tree_tarefas.selection()
        if not sel:
            return
        idx = self.tree_tarefas.index(sel[0])
        tarefa_atual = ManutencaoService.obter_tarefas(incluir_inativas=True)[idx]
        ManutencaoService.definir_ativa(tarefa_atual["id"], not tarefa_atual.get("ativo", True))
        self.atualizar_lista_tarefas()
        self.atualizar_agenda()

    # ==========================================
    # HISTÓRICO
    # ==========================================
    def construir_tab_historico(self):
        cols = ("maquina", "tarefa", "data", "operador", "notas")
        anchors = {"maquina": "w", "tarefa": "w", "data": "center", "operador": "w", "notas": "w"}
        self.tree_historico = ttk.Treeview(self.tab_historico, columns=cols, show="headings", height=16, style="Manutencao.Treeview")
        for c, h, w in [("maquina", "MÁQUINA", 130), ("tarefa", "TAREFA", 200), ("data", "DATA", 140), ("operador", "OPERADOR", 110), ("notas", "NOTAS", 180)]:
            self.tree_historico.heading(c, text=h, anchor=anchors[c])
            self.tree_historico.column(c, width=w, anchor=anchors[c])
        self.tree_historico.pack(fill="both", expand=True, pady=10)

    def atualizar_historico(self):
        for i in self.tree_historico.get_children():
            self.tree_historico.delete(i)

        maquinas_por_id = {m["id"]: m.get("nome", m["id"]) for m in MaquinaService.obter_todas()}
        tarefas_por_id = {t["id"]: t.get("nome", "") for t in ManutencaoService.obter_tarefas(incluir_inativas=True)}

        for h in ManutencaoService.obter_historico():
            self.tree_historico.insert("", "end", values=(
                maquinas_por_id.get(h.get("maquina_id"), h.get("maquina_id")),
                tarefas_por_id.get(h.get("tarefa_id"), "-"),
                h.get("data_realizacao", ""),
                h.get("operador", ""),
                h.get("notas", ""),
            ))
