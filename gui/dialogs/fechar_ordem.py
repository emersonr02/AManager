import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from config.constantes import DICIONARIO_NC
from services.producao_service import ProducaoService

class JanelaFecharOrdem(ctk.CTkToplevel):
    def __init__(self, parent, dados_log, callback_atualizar):
        super().__init__(parent)
        self.title(f"Gestão da Peça - ID {dados_log.get('id')}")
        self.geometry("500x480")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.dados_log = dados_log
        self.callback_atualizar = callback_atualizar
        self.criar_widgets()

    def mascara_tempo(self, event, widget):
        if event.keysym in ["BackSpace", "Delete", "Left", "Right", "Tab"]: return
        texto = widget.get().replace(":", "")
        texto = "".join([c for c in texto if c.isdigit()])
        if len(texto) >= 2:
            widget.delete(0, tk.END)
            widget.insert(0, f"{texto[:2]}:{texto[2:4]}")
        if len(widget.get()) > 5:
            widget.delete(5, tk.END)

    def criar_widgets(self):
        ctk.CTkLabel(self, text=f"Projeto: {self.dados_log.get('nr_projeto')}", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=10)
        
        frm_edit = ctk.CTkFrame(self)
        frm_edit.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(frm_edit, text="Corrigir Tempo Máquina (HH:MM):").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        self.ent_t = ctk.CTkEntry(frm_edit, width=150)
        self.ent_t.grid(row=0, column=1, padx=10, pady=5)
        self.ent_t.insert(0, self.dados_log.get("hora_maquina", "00:00"))
        self.ent_t.bind("<KeyRelease>", lambda e: self.mascara_tempo(e, self.ent_t))
        
        ctk.CTkLabel(frm_edit, text="Corrigir Quantidade Usada:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.ent_q = ctk.CTkEntry(frm_edit, width=150)
        self.ent_q.grid(row=1, column=1, padx=10, pady=5)
        self.ent_q.insert(0, str(self.dados_log.get("quantidade", 0.0)))

        ctk.CTkLabel(self, text="Selecione o Estado Final:").pack(pady=(15, 5))
        self.cmb_estado = ctk.CTkComboBox(self, values=["Em Andamento", "Concluída", "Falha"], command=self.alternar_painel_erros)
        self.cmb_estado.pack(pady=5)
        self.cmb_estado.set(self.dados_log.get("estado", "Em Andamento"))

        self.lbl_erro = ctk.CTkLabel(self, text="Causa Raiz (Cód NC CEiiA):")
        lista_erros = DICIONARIO_NC.get(self.dados_log.get("tecnologia", "FDM"), ["Outros Desvios Técnicos"])
        self.cmb_erros = ctk.CTkComboBox(self, values=lista_erros, width=400)

        if self.dados_log.get("estado") == "Falha":
            self.alternar_painel_erros("Falha")
            if self.dados_log.get("erro"): self.cmb_erros.set(self.dados_log["erro"])

        ctk.CTkButton(self, text="GUARDAR DADOS DE QUALIDADE", fg_color="#1f538d", font=ctk.CTkFont(weight="bold"), command=self.salvar_mudanca).pack(side="bottom", pady=20, fill="x", padx=40)

    def alternar_painel_erros(self, estado):
        if estado == "Falha":
            self.lbl_erro.pack(pady=(10, 5))
            self.cmb_erros.pack(pady=5)
        else:
            self.lbl_erro.pack_forget()
            self.cmb_erros.pack_forget()

    def salvar_mudanca(self):
        t_maq = self.ent_t.get().strip()
        if not ProducaoService.validar_formato_tempo(t_maq):
             messagebox.showerror("Erro de Validação", "O tempo deve estar no formato exato HH:MM.")
             return

        try: nova_q = float(self.ent_q.get().strip().replace(',', '.'))
        except ValueError:
            messagebox.showerror("Erro de Validação", "Quantidade inválida.")
            return

        est = self.cmb_estado.get()
        self.dados_log.update({
            "hora_maquina": t_maq,
            "quantidade": nova_q,
            "estado": est,
            "erro": self.cmb_erros.get() if est == "Falha" else ""
        })
        self.callback_atualizar(self.dados_log)
        self.destroy()