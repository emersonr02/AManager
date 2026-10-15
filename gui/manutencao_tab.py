import os
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk

from services.manutencao_service import ManutencaoService
from services.maquina_service import MaquinaService
from gui import theme

_VARIANTE_ESTADO = {"atrasada": "bad", "proxima": "warn", "ok": "ok", "sem_dados": "neutral"}
_LABEL_ESTADO = {"atrasada": "Atrasada", "proxima": "Próxima", "ok": "OK", "sem_dados": "Sem dados"}
_SEM_MODELOS = "Sem modelos registados"


def _num(v):
    return f"{v:g}" if isinstance(v, float) else str(v)


def texto_frequencia(freq_dias, freq_horas):
    partes = []
    if freq_dias:
        partes.append(f"{_num(freq_dias)} d")
    if freq_horas:
        partes.append(f"{_num(freq_horas)} h")
    return " / ".join(partes) or "—"


def texto_vencimento(linha):
    """"há 19 d" (atrasada) ou "em 5 d" — na dimensão mais urgente (dias ou
    horas de uso). Antes a agenda mostrava só os valores desde a última vez, e
    não se percebia a frequência nem quanto faltava."""
    if linha["estado"] == "sem_dados":
        return "sem produções"
    candidatos = []
    if linha.get("frequencia_dias") and linha.get("dias_desde") is not None:
        candidatos.append((linha["dias_desde"] / linha["frequencia_dias"], linha["frequencia_dias"] - linha["dias_desde"], "d"))
    if linha.get("frequencia_horas") and linha.get("horas_desde") is not None:
        candidatos.append((linha["horas_desde"] / linha["frequencia_horas"], linha["frequencia_horas"] - linha["horas_desde"], "h"))
    if not candidatos:
        return "—"
    _, restante, unidade = max(candidatos, key=lambda c: c[0])
    valor = int(round(abs(restante)))
    if restante < 0:
        return f"há {valor} {unidade}"
    if valor == 0:
        return "agora"
    return f"em {valor} {unidade}"


class ManutencaoTab:
    def __init__(self, parent_frame, f_padrao=None, f_titulo=None, master_app=None):
        self.parent = parent_frame
        self.master_app = master_app
        self.dialogo = None
        self.parent.configure(fg_color=theme.BG)

        self.construir_layout()
        self.atualizar_agenda()
        self.atualizar_lista_tarefas()
        self.atualizar_historico()

    def construir_layout(self):
        theme.page_header(self.parent, "Manutenção preventiva", "Manutenção").pack(fill="x", padx=24, pady=(18, 8))
        self.tabview = theme.tabview(self.parent)
        self.tabview.pack(fill="both", expand=True, padx=24, pady=(0, 18))
        self.tab_agenda = self.tabview.add("Agenda")
        self.tab_tarefas = self.tabview.add("Tarefas periódicas")
        self.tab_historico = self.tabview.add("Histórico")

        self.construir_tab_agenda()
        self.construir_tab_tarefas()
        self.construir_tab_historico()

    # ==========================================
    # AGENDA
    # ==========================================
    def construir_tab_agenda(self):
        ctk.CTkLabel(self.tab_agenda, text="Uma linha por máquina e tarefa do seu modelo, da mais urgente para a menos urgente.",
                     font=theme.font_body(12), text_color=theme.TEXT_MUTED, anchor="w").pack(fill="x", pady=(8, 4))
        frm_acoes = ctk.CTkFrame(self.tab_agenda, fg_color="transparent")
        frm_acoes.pack(side="bottom", fill="x", pady=(6, 8))
        self.btn_concluir = theme.button_primary(frm_acoes, text="Registar manutenção feita", height=36,
                                                 command=self.marcar_concluida)
        self.btn_concluir.pack(side="left")

        frm_tab, self.tree_agenda = theme.tabela(self.tab_agenda, [
            ("maquina", "Máquina", 170, "w"), ("tarefa", "Tarefa", 220, "w"),
            ("frequencia", "Frequência", 110, "center", False), ("desde", "Desde a última", 130, "center", False),
            ("vence", "Vence", 110, "center", False), ("estado", "Estado", 110, "w", False)])
        frm_tab.pack(fill="both", expand=True)
        self.agenda_pills = theme.TreeviewPillColumn(self.tree_agenda, "estado")
        self._sel_agenda = theme.ligar_a_selecao(self.tree_agenda, [self.btn_concluir])

    def atualizar_agenda(self):
        for i in self.tree_agenda.get_children():
            self.tree_agenda.delete(i)
        self._linhas_agenda = {}
        pill_dados = {}
        for linha in ManutencaoService.calcular_proximas_tarefas():
            desde = []
            if linha["dias_desde"] is not None:
                desde.append(f"{linha['dias_desde']} d")
            if linha["horas_desde"] is not None:
                desde.append(f"{linha['horas_desde']:.0f} h")
            estado_txt = _LABEL_ESTADO[linha["estado"]]
            item_id = self.tree_agenda.insert("", "end", values=(
                linha["maquina_nome"], linha["tarefa_nome"],
                texto_frequencia(linha.get("frequencia_dias"), linha.get("frequencia_horas")),
                " · ".join(desde) or "—", texto_vencimento(linha), estado_txt,
            ))
            pill_dados[item_id] = (estado_txt, _VARIANTE_ESTADO[linha["estado"]])
            self._linhas_agenda[item_id] = linha
        self.agenda_pills.definir_dados(pill_dados)
        self._sel_agenda()

    def marcar_concluida(self):
        sel = self.tree_agenda.selection()
        if not sel:
            return
        linha = self._linhas_agenda.get(sel[0])
        if linha:
            self.dialogo = JanelaConcluirManutencao(self.parent.winfo_toplevel(), linha, self._apos_registo)

    def _apos_registo(self):
        self.atualizar_agenda()
        self.atualizar_historico()

    # ==========================================
    # TAREFAS PERIÓDICAS
    # ==========================================
    def _modelos_disponiveis(self):
        modelos = sorted({m.get("modelo") for m in MaquinaService.obter_todas() if m.get("modelo")})
        return modelos if modelos else [_SEM_MODELOS]

    def construir_tab_tarefas(self):
        frm_form = ctk.CTkFrame(self.tab_tarefas, fg_color="transparent")
        frm_form.pack(fill="x", pady=(8, 6))

        def _col(rotulo, widget_fn):
            col = ctk.CTkFrame(frm_form, fg_color="transparent")
            col.pack(side="left", padx=(0, 10))
            theme.rotulo_campo(col, rotulo).pack(anchor="w", pady=(0, 3))
            w = widget_fn(col)
            w.pack(anchor="w")
            return w

        self.cmb_tarefa_modelo = _col("Modelo de máquina", lambda p: theme.combobox(p, values=self._modelos_disponiveis(), width=190, state="readonly"))
        self.ent_tarefa_nome = _col("Tarefa", lambda p: theme.entry(p, placeholder_text="ex.: Lubrificar eixos", width=200))
        self.ent_tarefa_freq_dias = _col("A cada (dias)", lambda p: theme.entry(p, placeholder_text="ex.: 30", width=100, font=theme.font_mono(12)))
        self.ent_tarefa_freq_horas = _col("Ou a cada (horas)", lambda p: theme.entry(p, placeholder_text="ex.: 200", width=110, font=theme.font_mono(12)))
        col_btn = ctk.CTkFrame(frm_form, fg_color="transparent")
        col_btn.pack(side="left", anchor="s")
        theme.button_action(col_btn, text="Adicionar tarefa", command=self.adicionar_tarefa, width=140).pack()

        frm_acoes = ctk.CTkFrame(self.tab_tarefas, fg_color="transparent")
        frm_acoes.pack(side="bottom", fill="x", pady=(6, 8))
        btn_editar = theme.button_ghost(frm_acoes, text="Editar", width=100, command=self.editar_tarefa_selecionada)
        btn_editar.pack(side="left", padx=(0, 10))
        btn_toggle = theme.button_secondary(frm_acoes, text="Ativar / desativar", width=150, command=self.toggle_ativa_tarefa)
        btn_toggle.pack(side="left")

        frm_tab, self.tree_tarefas = theme.tabela(self.tab_tarefas, [
            ("modelo", "Modelo", 180, "w"), ("nome", "Tarefa", 240, "w"),
            ("freq_dias", "A cada (dias)", 110, "center", False), ("freq_horas", "A cada (horas)", 120, "center", False),
            ("estado", "Estado", 100, "w", False)])
        frm_tab.pack(fill="both", expand=True)
        self.tree_tarefas.bind("<Double-1>", self.editar_tarefa_selecionada)
        self._sel_tarefas = theme.ligar_a_selecao(self.tree_tarefas, [btn_editar, btn_toggle])

    def atualizar_lista_tarefas(self):
        for i in self.tree_tarefas.get_children():
            self.tree_tarefas.delete(i)
        self._tarefas_por_item = {}
        for t in ManutencaoService.obter_tarefas(incluir_inativas=True):
            estado = "Ativa" if t.get("ativo", True) else "Inativa"
            item = self.tree_tarefas.insert("", "end", tags=("tag_ok" if estado == "Ativa" else "tag_muted",), values=(
                t["modelo"], t["nome"], t.get("frequencia_dias") or "-", t.get("frequencia_horas") or "-", estado,
            ))
            self._tarefas_por_item[item] = t
        if hasattr(self, "cmb_tarefa_modelo"):
            self.cmb_tarefa_modelo.configure(values=self._modelos_disponiveis())
        self._sel_tarefas()

    @staticmethod
    def _ler_frequencias(dias_str, horas_str):
        """(frequencia_dias, frequencia_horas) convertidos, ou ValueError com uma
        mensagem pronta a mostrar se algum campo preenchido não for um número."""
        freq_dias = freq_horas = None
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
        if not modelo or modelo == _SEM_MODELOS or not nome:
            messagebox.showwarning("Tarefa incompleta", "Escolha o modelo e preencha o nome da tarefa.")
            return
        try:
            freq_dias, freq_horas = self._ler_frequencias(self.ent_tarefa_freq_dias.get().strip(), self.ent_tarefa_freq_horas.get().strip())
        except ValueError as e:
            messagebox.showwarning("Frequência inválida", str(e))
            return
        try:
            ManutencaoService.criar_tarefa(modelo=modelo, nome=nome, frequencia_dias=freq_dias, frequencia_horas=freq_horas)
        except ValueError as e:
            messagebox.showerror("Não foi possível adicionar", str(e))
            return
        for ent in (self.ent_tarefa_nome, self.ent_tarefa_freq_dias, self.ent_tarefa_freq_horas):
            ent.delete(0, "end")
        self.atualizar_lista_tarefas()
        self.atualizar_agenda()
        theme.toast(self.parent, f"Tarefa \"{nome}\" adicionada para {modelo}.")

    def _tarefa_selecionada(self):
        sel = self.tree_tarefas.selection()
        return self._tarefas_por_item.get(sel[0]) if sel else None

    def editar_tarefa_selecionada(self, event=None):
        tarefa = self._tarefa_selecionada()
        if tarefa:
            self.dialogo = JanelaEditarTarefa(self.parent.winfo_toplevel(), tarefa, self._modelos_disponiveis(), self._apos_edicao)

    def _apos_edicao(self):
        self.atualizar_lista_tarefas()
        self.atualizar_agenda()

    def toggle_ativa_tarefa(self):
        tarefa = self._tarefa_selecionada()
        if tarefa:
            ManutencaoService.definir_ativa(tarefa["id"], not tarefa.get("ativo", True))
            self.atualizar_lista_tarefas()
            self.atualizar_agenda()

    # ==========================================
    # HISTÓRICO
    # ==========================================
    def construir_tab_historico(self):
        frm_tab, self.tree_historico = theme.tabela(self.tab_historico, [
            ("maquina", "Máquina", 170, "w"), ("tarefa", "Tarefa", 220, "w"), ("data", "Data", 140, "center", False),
            ("operador", "Operador", 110, "w", False), ("notas", "Notas", 220, "w")])
        frm_tab.pack(fill="both", expand=True, pady=(8, 8))

    def atualizar_historico(self):
        for i in self.tree_historico.get_children():
            self.tree_historico.delete(i)
        maquinas_por_id = {m["id"]: m.get("nome", m["id"]) for m in MaquinaService.obter_todas()}
        tarefas_por_id = {t["id"]: t.get("nome", "") for t in ManutencaoService.obter_tarefas(incluir_inativas=True)}
        for h in ManutencaoService.obter_historico():
            data = h.get("data_realizacao", "")
            try:
                data = datetime.strptime(data, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
            except ValueError:
                pass
            self.tree_historico.insert("", "end", values=(
                maquinas_por_id.get(h.get("maquina_id"), h.get("maquina_id")),
                tarefas_por_id.get(h.get("tarefa_id"), "-"),
                data, h.get("operador", ""), h.get("notas", ""),
            ))


class JanelaConcluirManutencao(theme.Dialogo):
    """Registo de uma manutenção feita — com confirmação e notas (antes era um
    clique direto, sem notas, e o Histórico tinha uma coluna Notas que a UI
    nunca preenchia)."""

    def __init__(self, parent, linha, ao_registar):
        self.linha = linha
        self._ao_registar = ao_registar
        super().__init__(parent, "Registar manutenção feita", largura=480, altura=340, texto_acao="Registar",
                         scroll=False, subtitulo=f"{linha['maquina_nome']} · {linha['tarefa_nome']}")
        self.operador = os.environ.get("USERNAME", "Desconhecido")
        self.rodape_info.configure(text=f"Registado por {self.operador}, agora")
        theme.rotulo_campo(self.corpo, "Notas (opcional)").pack(anchor="w", pady=(8, 2))
        self.ent_notas = theme.entry(self.corpo, placeholder_text="ex.: peça trocada, lote do consumível, observações")
        self.ent_notas.pack(fill="x")
        self.ent_notas.focus_set()

    def confirmar(self):
        ManutencaoService.registar_conclusao(self.linha["tarefa_id"], self.linha["maquina_id"], self.operador,
                                             notas=self.ent_notas.get().strip())
        theme.toast(self, f"Manutenção registada: {self.linha['maquina_nome']} · {self.linha['tarefa_nome']}.")
        self._ao_registar()
        self.destroy()


class JanelaEditarTarefa(theme.Dialogo):
    def __init__(self, parent, tarefa, modelos, ao_guardar):
        self.tarefa = tarefa
        self._ao_guardar = ao_guardar
        super().__init__(parent, f"Editar tarefa — {tarefa['nome']}", largura=440, altura=440,
                         subtitulo="Preencha pelo menos uma frequência (dias ou horas de uso).")
        corpo = ctk.CTkFrame(self.corpo, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=12)
        theme.rotulo_campo(corpo, "Nome", True).pack(anchor="w", pady=(8, 2))
        self.ent_nome = theme.entry(corpo)
        self.ent_nome.insert(0, tarefa["nome"])
        self.ent_nome.pack(fill="x")
        theme.rotulo_campo(corpo, "Modelo de máquina", True).pack(anchor="w", pady=(8, 2))
        self.cmb_modelo = theme.combobox(corpo, values=modelos, state="readonly")
        self.cmb_modelo.set(tarefa["modelo"])
        self.cmb_modelo.pack(fill="x")
        theme.rotulo_campo(corpo, "A cada (dias)").pack(anchor="w", pady=(8, 2))
        self.ent_dias = theme.entry(corpo, font=theme.font_mono(12))
        if tarefa.get("frequencia_dias"):
            self.ent_dias.insert(0, str(tarefa["frequencia_dias"]))
        self.ent_dias.pack(fill="x")
        theme.rotulo_campo(corpo, "Ou a cada (horas de uso)").pack(anchor="w", pady=(8, 2))
        self.ent_horas = theme.entry(corpo, font=theme.font_mono(12))
        if tarefa.get("frequencia_horas"):
            self.ent_horas.insert(0, str(tarefa["frequencia_horas"]))
        self.ent_horas.pack(fill="x")

    def confirmar(self):
        novo_nome = self.ent_nome.get().strip()
        if not self.cmb_modelo.get() or not novo_nome:
            messagebox.showwarning("Tarefa incompleta", "Preencha o modelo e o nome.")
            return
        try:
            freq_dias, freq_horas = ManutencaoTab._ler_frequencias(self.ent_dias.get().strip(), self.ent_horas.get().strip())
        except ValueError as e:
            messagebox.showwarning("Frequência inválida", str(e))
            return
        try:
            ManutencaoService.atualizar_tarefa({**self.tarefa, "modelo": self.cmb_modelo.get(), "nome": novo_nome,
                                                "frequencia_dias": freq_dias, "frequencia_horas": freq_horas})
        except ValueError as e:
            messagebox.showerror("Não foi possível guardar", str(e))
            return
        theme.toast(self, f"Tarefa \"{novo_nome}\" guardada.")
        self._ao_guardar()
        self.destroy()
