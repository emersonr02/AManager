import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

# Importa o serviço de falhas e o serviço de produção (para validar o formato de horas)
from services.nc_service import NCService
from services.producao_service import ProducaoService

class JanelaFecharOrdem(ctk.CTkToplevel):
    def __init__(self, parent, log_dados, callback_salvar):
        super().__init__(parent)
        self.log_dados = log_dados
        self.callback_salvar = callback_salvar
        
        self.title(f"Tratamento da Ordem #{log_dados.get('id')}")
        self.geometry("600x780") # Janela ligeiramente mais alta para caber o apontamento real
        self.configure(fg_color="#fcfcfc")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()

        self.construir_layout()
        
    def construir_layout(self):
        # Título principal
        ctk.CTkLabel(self, text=f"Tratamento e Fecho - Ordem #{self.log_dados.get('id')}", font=("Arial", 16, "bold"), text_color="#1f538d").pack(pady=10)

        # --- 1. RESUMO DA ORDEM (Somente Leitura) ---
        frm_resumo = ctk.CTkFrame(self, fg_color="#f0f2f5", corner_radius=8)
        frm_resumo.pack(fill="x", padx=30, pady=5)
        
        ctk.CTkLabel(frm_resumo, text="Resumo do Planeamento:", font=("Arial", 12, "bold"), text_color="gray40").pack(anchor="w", padx=15, pady=(10, 0))
        
        info_texto = f"Máquina: {self.log_dados.get('id_maquina')}  |  Projeto: {self.log_dados.get('nr_projeto')}\n"
        info_texto += f"Material: {self.log_dados.get('material')}  |  Tecnologia: {self.log_dados.get('tecnologia')}\n"
        info_texto += f"Tempo Est.: {self.log_dados.get('hora_maquina')}  |  Qtd Est.: {self.log_dados.get('quantidade')} g/ml"
        
        ctk.CTkLabel(frm_resumo, text=info_texto, font=("Arial", 12), text_color="black", justify="left").pack(anchor="w", padx=15, pady=(5, 10))

        # --- 2. DADOS REAIS DE PRODUÇÃO ---
        frm_reais = ctk.CTkFrame(self, fg_color="white", border_width=1, border_color="#e0e0e0", corner_radius=8)
        frm_reais.pack(fill="x", padx=30, pady=10)
        
        ctk.CTkLabel(frm_reais, text="Apontamento Real de Produção:", font=("Arial", 12, "bold"), text_color="#1f538d").grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 5))
        
        ctk.CTkLabel(frm_reais, text="Tempo Real (HH:MM):", font=("Arial", 12), text_color="gray40").grid(row=1, column=0, sticky="e", padx=10, pady=5)
        self.ent_tempo_real = ctk.CTkEntry(frm_reais, font=("Arial", 12), width=120, fg_color="#f0f2f5", text_color="black", border_color="gray80")
        self.ent_tempo_real.grid(row=1, column=1, sticky="w", padx=10, pady=5)
        self.ent_tempo_real.bind("<KeyRelease>", self.mascara_tempo)
        # Preenche com a estimativa para facilitar a vida do operador
        self.ent_tempo_real.insert(0, self.log_dados.get('tempo_real', self.log_dados.get('hora_maquina', '00:00')))

        ctk.CTkLabel(frm_reais, text="Quantidade Real (g/ml):", font=("Arial", 12), text_color="gray40").grid(row=2, column=0, sticky="e", padx=10, pady=5)
        self.ent_qtd_real = ctk.CTkEntry(frm_reais, font=("Arial", 12), width=120, fg_color="#f0f2f5", text_color="black", border_color="gray80")
        self.ent_qtd_real.grid(row=2, column=1, sticky="w", padx=10, pady=5)
        # Preenche com a estimativa
        self.ent_qtd_real.insert(0, str(self.log_dados.get('quantidade_real', self.log_dados.get('quantidade', '0'))))

        # --- 3. ESTADO FINAL ---
        ctk.CTkLabel(self, text="Estado Final da Ordem:", font=("Arial", 12, "bold"), text_color="gray30").pack(anchor="w", padx=35, pady=(10, 0))
        self.cmb_estado = ctk.CTkComboBox(self, values=["Concluída", "Cancelada"], font=("Arial", 12), fg_color="white", border_color="gray80", text_color="black", button_color="#1f538d", state="readonly", command=self.alternar_modo_estado)
        self.cmb_estado.pack(fill="x", padx=35, pady=5)
        estado_atual = self.log_dados.get("estado", "Concluída")
        self.cmb_estado.set("Cancelada" if estado_atual == "Falha" else estado_atual)

# --- 4. CONTROLO DE QUALIDADE (Lê o estado guardado no JSON) ---
        self.frm_qualidade = ctk.CTkFrame(self, fg_color="#f8f9fa", corner_radius=8, border_width=1, border_color="#e0e0e0")
        self.frm_qualidade.pack(fill="x", padx=30, pady=10)
        
        ctk.CTkLabel(self.frm_qualidade, text="Critérios de Aceitação (Controlo de Qualidade):", font=("Arial", 11, "bold"), text_color="gray40").pack(anchor="w", padx=15, pady=(10, 5))
        
        frm_checks = ctk.CTkFrame(self.frm_qualidade, fg_color="transparent")
        frm_checks.pack(fill="x", padx=10, pady=(0, 10))

        # CORREÇÃO: Agora puxa o estado gravado (True/False). Se não existir, nasce a False.
        self.chk_var_visual = tk.BooleanVar(value=self.log_dados.get("inspecao_visual", False))
        self.chk_var_dim = tk.BooleanVar(value=self.log_dados.get("controlo_dimensional", False))
        self.chk_var_conf = tk.BooleanVar(value=self.log_dados.get("conformidade_peca", False))

        ctk.CTkCheckBox(frm_checks, text="Inspeção\nVisual", font=("Arial", 11), variable=self.chk_var_visual).pack(side="left", expand=True, padx=5)
        ctk.CTkCheckBox(frm_checks, text="Controlo\nDimensional", font=("Arial", 11), variable=self.chk_var_dim).pack(side="left", expand=True, padx=5)
        ctk.CTkCheckBox(frm_checks, text="Conformidade\ndas Peças", font=("Arial", 11), variable=self.chk_var_conf).pack(side="left", expand=True, padx=5)

        # --- 5. CANCELAMENTO E CATÁLOGO DE FALHAS ---
        self.frm_erro = ctk.CTkFrame(self, fg_color="transparent")
        
        ctk.CTkLabel(self.frm_erro, text="Motivo do Cancelamento / Não Conformidade:", font=("Arial", 12, "bold"), text_color="#A12222").pack(anchor="w", pady=(5, 0))
        
        # CORREÇÃO: Uso do .strip() para evitar erros de espaços em branco ("FDM " vs "FDM")
        tecnologia_peca = str(self.log_dados.get("tecnologia", "FDM")).strip()
        motivos_lista = ["Erro Humano / Operador", "Queda de Energia", "Descolamento da Mesa (Genérico)"]
        motivos_lista.extend(NCService.obter_nc_por_tecnologia(tecnologia_peca))
        
        self.cmb_erro = ctk.CTkComboBox(self.frm_erro, values=motivos_lista, font=("Arial", 12), fg_color="white", border_color="gray80", text_color="black", state="readonly", command=self.mostrar_acoes_corretivas)
        self.cmb_erro.pack(fill="x", pady=5)

        ctk.CTkLabel(self.frm_erro, text="Ação Corretiva Sugerida:", font=("Arial", 11, "bold"), text_color="gray40").pack(anchor="w", pady=(10, 0))
        self.txt_acao = ctk.CTkTextbox(self.frm_erro, height=90, font=("Arial", 11), fg_color="#f0f2f5", text_color="#1f538d", border_width=1, border_color="#e0e0e0")
        self.txt_acao.pack(fill="x", pady=5)
        self.txt_acao.insert("1.0", "Selecione uma Não Conformidade (COD) acima para ver as instruções...")
        self.txt_acao.configure(state="disabled")

        # CORREÇÃO: Força a Combobox a exibir o erro que estava guardado
        erro_guardado = self.log_dados.get("erro", "")
        if erro_guardado and erro_guardado in motivos_lista:
            self.cmb_erro.set(erro_guardado)
        elif motivos_lista:
            self.cmb_erro.set(motivos_lista[0])

        # --- BOTÃO SALVAR ---
        self.btn_salvar = ctk.CTkButton(self, text="SALVAR APONTAMENTO E FECHAR", fg_color="#1f538d", hover_color="#143a63", text_color="white", font=("Arial", 13, "bold"), command=self.gravar_fecho, height=45)
        self.btn_salvar.pack(fill="x", padx=30, pady=20)

        # Atualiza a visibilidade dos frames
        self.alternar_modo_estado()
        
        # CORREÇÃO: Se a ordem já estava "Cancelada", carrega automaticamente o texto da Ação Corretiva
        if self.cmb_estado.get() == "Cancelada" and erro_guardado:
            self.mostrar_acoes_corretivas(erro_guardado)

    def mascara_tempo(self, event):
        widget = event.widget
        if event.keysym in ["BackSpace", "Delete", "Left", "Right", "Tab"]: return
        texto = widget.get().replace(":", "")
        texto = "".join([c for c in texto if c.isdigit()])
        if len(texto) >= 2:
            widget.delete(0, tk.END)
            widget.insert(0, f"{texto[:2]}:{texto[2:4]}")
        if len(widget.get()) > 5:
            widget.delete(5, tk.END)

    def alternar_modo_estado(self, event=None):
        if self.cmb_estado.get() == "Cancelada":
            # Exibe antes do botão de salvar
            self.frm_erro.pack(fill="x", padx=30, pady=5, before=self.btn_salvar)
        else:
            self.frm_erro.pack_forget()

    def mostrar_acoes_corretivas(self, selecao):
        self.txt_acao.configure(state="normal")
        self.txt_acao.delete("1.0", tk.END)
        
        if selecao.startswith("COD"):
            codigo_nc = selecao.split(" - ")[0]
            acoes = NCService.obter_acoes_por_cod(codigo_nc)
            
            if acoes:
                texto_final = ""
                for acao in acoes:
                    texto_final += f"🔧 {acao.get('act')} - {acao.get('acao')}\n"
                    for etapa in acao.get("etapas", []):
                        texto_final += f"   {etapa}\n"
                    texto_final += "\n"
                self.txt_acao.insert("1.0", texto_final.strip())
            else:
                self.txt_acao.insert("1.0", "Nenhuma ação corretiva específica registada.")
        else:
            self.txt_acao.insert("1.0", "Erro genérico. Siga o procedimento padrão do laboratório CEiiA.")
            
        self.txt_acao.configure(state="disabled")

    def gravar_fecho(self):
        estado_final = self.cmb_estado.get()
        t_real = self.ent_tempo_real.get().strip()
        q_real = self.ent_qtd_real.get().strip()

        # Validação do Tempo Real
        if not ProducaoService.validar_formato_tempo(t_real):
            messagebox.showerror("Erro de Formato", "O tempo real deve estar no formato exato HH:MM.")
            return
        
        # Validação numéria da Quantidade Real
        try:
            q_real_float = float(q_real.replace(',', '.'))
        except ValueError:
            messagebox.showerror("Erro", "A quantidade real deve ser um número válido.")
            return

        qualidade_aprovada = self.chk_var_visual.get() and self.chk_var_dim.get() and self.chk_var_conf.get()

        if estado_final == "Concluída" and not qualidade_aprovada:
            messagebox.showerror("Erro de Qualidade", "Para concluir uma ordem, é obrigatório validar os 3 critérios de aceitação. Se a peça tem defeito, altere o status para 'Cancelada'.")
            return

        # Guarda os apontamentos reais no dicionário do JSON
        self.log_dados["tempo_real"] = t_real
        self.log_dados["quantidade_real"] = q_real_float
        self.log_dados["estado"] = estado_final
        
        if estado_final == "Cancelada":
            self.log_dados["erro"] = self.cmb_erro.get()
            self.log_dados["inspecao_visual"] = self.chk_var_visual.get()
            self.log_dados["controlo_dimensional"] = self.chk_var_dim.get()
            self.log_dados["conformidade_peca"] = self.chk_var_conf.get()
        else:
            self.log_dados["erro"] = ""
            self.log_dados["inspecao_visual"] = True
            self.log_dados["controlo_dimensional"] = True
            self.log_dados["conformidade_peca"] = True

        self.callback_salvar(self.log_dados)
        self.destroy()