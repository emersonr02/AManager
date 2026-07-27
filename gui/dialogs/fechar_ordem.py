import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

class JanelaFecharOrdem(ctk.CTkToplevel):
    def __init__(self, parent, log_dados, callback_salvar):
        super().__init__(parent)
        self.log_dados = log_dados
        self.callback_salvar = callback_salvar
        
        self.title(f"Tratamento da Ordem #{log_dados.get('id')}")
        self.geometry("500x450")
        self.configure(fg_color="#fcfcfc")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()

        # Título
        ctk.CTkLabel(self, text=f"Encerrar Produção - Ordem #{log_dados.get('id')}", font=("Arial", 16, "bold"), text_color="#1f538d").pack(pady=15)

        # 1. COMBOBOX DE ESTADO FINAL
        ctk.CTkLabel(self, text="Estado Final da Ordem:", font=("Arial", 12, "bold"), text_color="gray30").pack(anchor="w", padx=40, pady=(10, 0))
        self.cmb_estado = ctk.CTkComboBox(
            self, 
            values=["Concluída", "Falha"], 
            font=("Arial", 12), 
            fg_color="white", 
            border_color="gray80", 
            text_color="black", 
            button_color="#1f538d", 
            state="readonly",
            command=self.alternar_modo_estado
        )
        self.cmb_estado.pack(fill="x", padx=40, pady=5)
        self.cmb_estado.set(log_dados.get("estado", "Concluída"))

        # --- SECCÃO DE CONTROLO DE QUALIDADE ---
        # Container para agrupar os três checks da imagem
        self.frm_qualidade = ctk.CTkFrame(self, fg_color="#f8f9fa", corner_radius=8, border_width=1, border_color="#e0e0e0")
        self.frm_qualidade.pack(fill="x", padx=40, pady=15)
        
        ctk.CTkLabel(self.frm_qualidade, text="Critérios de Aceitação (Controlo de Qualidade):", font=("Arial", 11, "bold"), text_color="gray40").pack(anchor="w", padx=15, pady=(10, 5))
        
        frm_checks_row = ctk.CTkFrame(self.frm_qualidade, fg_color="transparent")
        frm_checks_row.pack(fill="x", padx=10, pady=(0, 10))

        # Variáveis de controlo (Nascem como TRUE / Ativos)
        self.chk_var_visual = tk.BooleanVar(value=True)
        self.chk_var_dim = tk.BooleanVar(value=True)
        self.chk_var_conf = tk.BooleanVar(value=True)

        self.chk_visual = ctk.CTkCheckBox(frm_checks_row, text="Inspeção\nVisual", font=("Arial", 11), variable=self.chk_var_visual, command=self.validar_checks_qualidade)
        self.chk_visual.pack(side="left", expand=True, padx=5)

        self.chk_dim = ctk.CTkCheckBox(frm_checks_row, text="Controlo\nDimensional", font=("Arial", 11), variable=self.chk_var_dim, command=self.validar_checks_qualidade)
        self.chk_dim.pack(side="left", expand=True, padx=5)

        self.chk_conf = ctk.CTkCheckBox(frm_checks_row, text="Conformidade\ndas Peças", font=("Arial", 11), variable=self.chk_var_conf, command=self.validar_checks_qualidade)
        self.chk_conf.pack(side="left", expand=True, padx=5)

        # 2. CAMPO DE ERRO (Só aparece se o estado for mudado para "Falha")
        self.lbl_erro = ctk.CTkLabel(self, text="Código/Motivo da Falha:", font=("Arial", 12, "bold"), text_color="gray30")
        self.cmb_erro = ctk.CTkComboBox(self, values=["Queda de Energia", "Descolamento da Mesa", "Subextrusão / Entupimento", "Erro de Fatiamento"], font=("Arial", 12), fg_color="white", border_color="gray80", text_color="black", state="readonly")

        # Botão de Salvar (Azul CEiiA)
        self.btn_salvar = ctk.CTkButton(self, text="SALVAR ATUALIZAÇÃO", fg_color="#1f538d", hover_color="#143a63", text_color="white", font=("Arial", 13, "bold"), command=self.gravar_fecho)
        self.btn_salvar.pack(fill="x", padx=40, pady=25)

        # Inicializa o estado visual correto com base no registo atual
        self.alternar_modo_estado()

    def validar_checks_qualidade(self, event=None):
        """ Se o operador desmarcar qualquer check, o sistema sugere mudar o estado para Falha """
        qualidade_aprovada = self.chk_var_visual.get() and self.chk_var_dim.get() and self.chk_var_conf.get()
        
        if not qualidade_aprovada:
            # Se desmarcou, muda automaticamente o combo para "Falha" para guiar o operador
            self.cmb_estado.set("Falha")
            self.alternar_modo_estado()

    def alternar_modo_estado(self, event=None):
        """ Controla o que aparece na tela dinamicamente """
        if self.cmb_estado.get() == "Falha":
            # Mostra o campo de erro
            self.lbl_erro.pack(anchor="w", padx=40, pady=(5, 0))
            self.cmb_erro.pack(fill="x", padx=40, pady=5)
        else:
            # Esconde o campo de erro se for Concluída
            self.lbl_erro.pack_forget()
            self.cmb_erro.pack_forget()

    def gravar_fecho(self):
        estado_final = self.cmb_estado.get()
        qualidade_aprovada = self.chk_var_visual.get() and self.chk_var_dim.get() and self.chk_var_conf.get()

        # Validação de consistência do MES: Não pode salvar como Concluída se algum check falhou
        if estado_final == "Concluída" and not qualidade_aprovada:
            messagebox.showerror("Erro de Qualidade", "Não pode concluir uma ordem se houver falhas nos critérios de aceitação. Altere o estado para 'Falha' ou reveja os testes.")
            return

        # Atualiza o dicionário de logs do JSON
        self.log_dados["estado"] = estado_final
        if estado_final == "Falha":
            self.log_dados["erro"] = self.cmb_erro.get()
            # Guarda no registo quais os checks que reprovaram, se quiseres auditar depois
            self.log_dados["inspecao_visual"] = self.chk_var_visual.get()
            self.log_dados["controlo_dimensional"] = self.chk_var_dim.get()
            self.log_dados["conformidade_peca"] = self.chk_var_conf.get()
        else:
            self.log_dados["erro"] = ""
            self.log_dados["inspecao_visual"] = True
            self.log_dados["controlo_dimensional"] = True
            self.log_dados["conformidade_peca"] = True

        # Dispara o callback para atualizar o JSON local e a Treeview do dashboard
        self.callback_salvar(self.log_dados)
        self.destroy()