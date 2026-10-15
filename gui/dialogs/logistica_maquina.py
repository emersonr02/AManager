from tkinter import messagebox

import customtkinter as ctk

from services.maquina_service import MaquinaService
from gui import theme

_ESTADOS = ["Operacional", "Manutenção - Parado", "Desativado"]


class JanelaLogisticaMaquina(theme.Dialogo):
    def __init__(self, parent, maquina_dados, callback_atualizar, f_padrao=None, f_titulo=None):
        self.maquina_dados = maquina_dados  # None -> registo novo; preenchido -> edição
        self.callback = callback_atualizar
        titulo = "Nova máquina" if not maquina_dados else f"Editar máquina {maquina_dados.get('id')}"
        super().__init__(parent, titulo, largura=460, altura=660, texto_acao="Guardar máquina",
                         subtitulo="Campos com * são obrigatórios.")
        self.btn_gravar = self.btn_acao

        corpo = ctk.CTkFrame(self.corpo, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=12)

        def _campo(rotulo, widget, obrigatorio=False, ajuda=""):
            theme.rotulo_campo(corpo, rotulo, obrigatorio).pack(anchor="w", pady=(10, 2))
            widget.pack(fill="x")
            if ajuda:
                ctk.CTkLabel(corpo, text=ajuda, font=theme.font_body(11), text_color=theme.TEXT_MUTED,
                             anchor="w").pack(anchor="w")
            return widget

        self.ent_id = _campo("ID do ativo", theme.entry(corpo, font=theme.font_mono(13), placeholder_text="ex.: X1C-4"), True)
        self.ent_nome = _campo("Nome", theme.entry(corpo, placeholder_text="ex.: Bambu Lab X1C #4"), True)
        self.ent_modelo = _campo("Modelo", theme.entry(corpo, placeholder_text="ex.: Bambu Lab X1C"),
                                 ajuda="Igual em todas as unidades do mesmo modelo (partilham tarefas de manutenção).")
        self.cmb_tech = _campo("Tecnologia", theme.combobox(corpo, values=["FDM", "SLA", "SLS"], state="readonly"), True)
        self.cmb_est = _campo("Estado", theme.combobox(corpo, values=_ESTADOS, state="readonly"), True)
        self.cmb_est.set("Operacional")
        self.ent_notas = _campo("Notas de manutenção / diagnóstico", theme.entry(corpo))
        self.ent_notas.insert(0, "OK")
        self.ent_url_img = _campo("Imagem (URL)", theme.entry(corpo, placeholder_text="https://…/imagem.png"))

        if self.maquina_dados:
            self.ent_id.insert(0, self.maquina_dados.get("id", ""))
            self.ent_id.configure(state="disabled")  # o ID é a chave primária
            self.ent_nome.insert(0, self.maquina_dados.get("nome", ""))
            self.ent_modelo.insert(0, self.maquina_dados.get("modelo", ""))
            if self.maquina_dados.get("tech") in ("FDM", "SLA", "SLS"):
                self.cmb_tech.set(self.maquina_dados["tech"])
            self.cmb_est.set(self.maquina_dados.get("estado", "Operacional"))
            self.ent_notas.delete(0, ctk.END)
            self.ent_notas.insert(0, self.maquina_dados.get("manutencao", "OK"))
            self.ent_url_img.insert(0, self.maquina_dados.get("url_img", ""))

            self.btn_remover = theme.button_danger(self.rodape_esquerda, text="Eliminar", height=38, width=100,
                                                   command=self.remover)
            self.btn_remover.pack(side="left")

    def confirmar(self):
        self.gravar()

    def gravar(self):
        mid = self.ent_id.get().strip()
        nome = self.ent_nome.get().strip()
        tech = self.cmb_tech.get()

        erros = []
        if not mid:
            erros.append("Indique o ID do ativo.")
        if not nome:
            erros.append("Indique o nome.")
        if tech not in ("FDM", "SLA", "SLS"):
            erros.append("Escolha a tecnologia — sem ela a máquina nunca aparece em Nova ordem.")
        if erros:
            messagebox.showwarning("Máquina incompleta", "\n".join(f"• {e}" for e in erros))
            return

        notas = self.ent_notas.get().strip()
        MaquinaService.salvar_maquina(
            mid=mid,
            nome=nome,
            tech=tech,
            estado=self.cmb_est.get(),
            manutencao=notas if notas else "OK",
            url_img=self.ent_url_img.get().strip(),
            modelo=self.ent_modelo.get().strip(),
        )
        theme.toast(self, f"Máquina {mid} guardada.")
        self.callback()
        self.destroy()

    def remover(self):
        """Eliminar só é permitido a máquinas sem histórico: as ordens antigas
        referem a máquina pelo nome e ficariam órfãs. Com histórico, o caminho
        é o estado "Desativado" (deixa de ser oferecida em Nova ordem)."""
        from services.producao_service import ProducaoService

        nome = self.maquina_dados.get("nome")
        mid = self.maquina_dados.get("id")
        n_ordens = sum(1 for p in ProducaoService.obter_todos(incluir_anuladas=True)
                       if p.get("maquina") == nome or p.get("id_maquina") == mid)
        if n_ordens:
            messagebox.showwarning(
                "Máquina com histórico",
                f"{nome} tem {n_ordens} ordem(ns) de produção registada(s) — eliminá-la deixaria esse "
                "histórico sem máquina.\n\nMude o estado para \"Desativado\": deixa de aparecer em "
                "Nova ordem e mantém o histórico.")
            return
        if messagebox.askyesno("Eliminar máquina",
                               f"Eliminar a máquina {mid} do parque?\nEsta ação não pode ser desfeita."):
            MaquinaService.remover_maquina(mid)
            theme.toast(self, f"Máquina {mid} eliminada.", "info")
            self.callback()
            self.destroy()
