import customtkinter as ctk
from tkinter import messagebox
from services.maquina_service import MaquinaService

class JanelaLogisticaMaquina(ctk.CTkToplevel):
    def __init__(self, parent, maquina_dados, callback_atualizar, f_padrao, f_titulo):
        super().__init__(parent)
        self.maquina_dados = maquina_dados  # Se for None -> Cadastro. Se vier preenchido -> Edição.
        self.callback = callback_atualizar
        self.f_padrao = f_padrao
        
        self.title("Cadastro de Ativo" if not maquina_dados else f"Modificar Ativo - {maquina_dados.get('id')}")
        self.geometry("420x600")
        self.resizable(False, False)
        
        # Configuração do fundo branco para bater com o novo padrão UI/UX claro
        self.configure(fg_color="#fcfcfc")
        
        # Garante que a janela fica focada à frente da principal
        self.transient(parent)
        self.grab_set()

        ctk.CTkLabel(self, text="Informações do Ativo", font=f_titulo, text_color="#1f538d").pack(pady=15)

        # Campo: ID da Máquina
        ctk.CTkLabel(self, text="ID Único do Ativo (Ex: X1C-4):", font=f_padrao, text_color="gray30").pack(anchor="w", padx=30, pady=(10, 0))
        self.ent_id = ctk.CTkEntry(self, font=f_padrao, fg_color="white", border_color="gray80", text_color="black")
        self.ent_id.pack(fill="x", padx=30, pady=5)

        # Campo: Nome Descritivo
        ctk.CTkLabel(self, text="Nome Descritivo:", font=f_padrao, text_color="gray30").pack(anchor="w", padx=30, pady=(10, 0))
        self.ent_nome = ctk.CTkEntry(self, font=f_padrao, fg_color="white", border_color="gray80", text_color="black")
        self.ent_nome.pack(fill="x", padx=30, pady=5)

        # Campo: Tecnologia AM
        ctk.CTkLabel(self, text="Tecnologia AM:", font=f_padrao, text_color="gray30").pack(anchor="w", padx=30, pady=(10, 0))
        self.cmb_tech = ctk.CTkComboBox(self, values=["FDM", "SLA", "SLS"], font=f_padrao, fg_color="white", border_color="gray80", text_color="black", button_color="#1f538d", state="readonly")
        self.cmb_tech.pack(fill="x", padx=30, pady=5)

        # Campo: Status Operacional
        ctk.CTkLabel(self, text="Status Operacional:", font=f_padrao, text_color="gray30").pack(anchor="w", padx=30, pady=(10, 0))
        self.cmb_est = ctk.CTkComboBox(self, values=["Operacional", "Manutenção - Parado", "Desativado"], font=f_padrao, fg_color="white", border_color="gray80", text_color="black", button_color="#1f538d", state="readonly")
        self.cmb_est.pack(fill="x", padx=30, pady=5)

        # Campo: Notas de Manutenção
        ctk.CTkLabel(self, text="Notas de Manutenção / Diagnóstico:", font=f_padrao, text_color="gray30").pack(anchor="w", padx=30, pady=(10, 0))
        self.ent_notas = ctk.CTkEntry(self, font=f_padrao, fg_color="white", border_color="gray80", text_color="black")
        self.ent_notas.pack(fill="x", padx=30, pady=5)
        self.ent_notas.insert(0, "OK")

        # NOVO CAMPO: URL da Miniatura (Pedido para as imagens das impressoras)
        ctk.CTkLabel(self, text="URL da Miniatura da Máquina:", font=f_padrao, text_color="gray30").pack(anchor="w", padx=30, pady=(10, 0))
        self.ent_url_img = ctk.CTkEntry(self, font=f_padrao, fg_color="white", border_color="gray80", text_color="black", placeholder_text="https://site.com/imagem.png")
        self.ent_url_img.pack(fill="x", padx=30, pady=5)

        # Se for um modo de Edição de uma máquina já existente, preenche os dados automáticos
        if self.maquina_dados:
            self.ent_id.insert(0, self.maquina_dados.get("id", ""))
            self.ent_id.configure(state="disabled") # Bloqueia a edição do ID primário
            
            self.ent_nome.insert(0, self.maquina_dados.get("nome", ""))
            self.cmb_tech.set(self.maquina_dados.get("tech", "FDM"))
            self.cmb_est.set(self.maquina_dados.get("estado", "Operacional"))
            
            self.ent_notas.delete(0, ctk.END)
            self.ent_notas.insert(0, self.maquina_dados.get("manutencao", "OK"))
            
            self.ent_url_img.insert(0, self.maquina_dados.get("url_img", ""))

        # Botão Principal: Gravar (Estilizado com o Azul CEiiA)
        ctk.CTkButton(self, text="GRAVAR ATIVO", fg_color="#1f538d", hover_color="#143a63", text_color="white", font=f_titulo, command=self.gravar).pack(fill="x", padx=30, pady=(25, 10))

        # Botão Secundário: Remover (Só aparece se o operador estiver a editar uma máquina existente)
        if self.maquina_dados:
            ctk.CTkButton(self, text="ELIMINAR ATIVO DO PARQUE", fg_color="#A12222", hover_color="#7F1A1A", text_color="white", font=f_padrao, command=self.remover).pack(fill="x", padx=30, pady=5)

    def gravar(self):
        mid = self.ent_id.get().strip()
        nome = self.ent_nome.get().strip()
        notas = self.ent_notas.get().strip()
        url_img = self.ent_url_img.get().strip()
        
        if not mid or not nome:
            messagebox.showwarning("Aviso", "Preencha o ID e o Nome do ativo antes de salvar.")
            return

        # Envia todos os dados recolhidos para o serviço tratar a persistência no JSON
        MaquinaService.salvar_maquina(
            mid=mid, 
            nome=nome, 
            tech=self.cmb_tech.get(),
            estado=self.cmb_est.get(), 
            manutencao=notas if notas else "OK",
            url_img=url_img
        )
        
        self.callback() # Atualiza o mosaico de cards na tela principal imediatamente
        self.destroy()

    def remover(self):
        if messagebox.askyesno("Confirmação de Engenharia", f"Tem a certeza que deseja remover permanentemente o ativo {self.maquina_dados.get('id')} do parque?"):
            MaquinaService.remover_maquina(self.maquina_dados.get("id"))
            self.callback() # Redesenha o mosaico sem a máquina removida
            self.destroy()