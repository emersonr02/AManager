import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import re
from database.json_manager import JSONManager

class JanelaGestaoSimples(ctk.CTkToplevel):
    def __init__(self, parent, titulo, placeholder_id, placeholder_nome, arquivo_alvo, callback_atualizar):
        super().__init__(parent)
        self.title(titulo)
        self.geometry("450x500")
        self.transient(parent)
        self.grab_set()
        
        self.arquivo_alvo = arquivo_alvo
        self.callback = callback_atualizar
        
        self.ent_id = ctk.CTkEntry(self, placeholder_text=placeholder_id)
        self.ent_id.pack(pady=(20, 5), padx=20, fill="x")
        self.ent_nome = ctk.CTkEntry(self, placeholder_text=placeholder_nome)
        self.ent_nome.pack(pady=5, padx=20, fill="x")

        ctk.CTkButton(self, text="Adicionar à Lista", command=self.adicionar_item).pack(pady=10, padx=20, fill="x")

        self.lista = tk.Listbox(self, bg="#2b2b2b", fg="white", font=("Arial", 11), selectbackground="#1f538d")
        self.lista.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.carregar_lista()
        ctk.CTkButton(self, text="Remover Selecionado", fg_color="#A12222", command=self.remover_item).pack(pady=(0, 20), padx=20, fill="x")

    def carregar_lista(self):
        self.lista.delete(0, tk.END)
        for item in JSONManager.carregar(self.arquivo_alvo): 
            self.lista.insert(tk.END, item)

    def adicionar_item(self):
        id_val = self.ent_id.get().strip()
        nome = self.ent_nome.get().strip()
        if not id_val or not nome: return
        
        if "projetos" in self.arquivo_alvo and not re.match(r"^\d{6}$", id_val):
            messagebox.showwarning("Engenharia", "O ID do projeto CEiiA tem de conter estritamente 6 algarismos.")
            return

        novo_item = f"{id_val} - {nome}"
        dados = JSONManager.carregar(self.arquivo_alvo)
        
        if novo_item not in dados:
            dados.append(novo_item)
            JSONManager.salvar(dados, self.arquivo_alvo)
            self.ent_id.delete(0, tk.END)
            self.ent_nome.delete(0, tk.END)
            self.carregar_lista()
            self.callback()

    def remover_item(self):
        sel = self.lista.curselection()
        if not sel: return
        item = self.lista.get(sel[0])
        dados = JSONManager.carregar(self.arquivo_alvo)
        
        if item in dados:
            dados.remove(item)
            JSONManager.salvar(dados, self.arquivo_alvo)
            self.carregar_lista()
            self.callback()