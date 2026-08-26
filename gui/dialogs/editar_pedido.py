import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from services.pedido_service import PedidoService
from services.projeto_service import ProjetoService
from services.material_service import MaterialService
from services.audit_service import AuditService
from gui import theme

class JanelaEditarPedido(ctk.CTkToplevel):
    def __init__(self, parent, pedido, callback_atualizar):
        super().__init__(parent)
        self.pedido = pedido
        # Cópia do estado original para alimentar a trilha de auditoria
        self._dados_antes_da_edicao = dict(pedido)
        self.callback_atualizar = callback_atualizar

        self.title(f"Editar Pedido #{PedidoService.formatar_codigo(self.pedido.get('id'))}")
        self.geometry("820x820")
        self.configure(fg_color=theme.BG)
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()

        self.linhas_pecas = [] 
        self.carregar_dados_auxiliares()
        self.construir_layout()
        self.preencher_dados_existentes()

    def carregar_dados_auxiliares(self):
        # 1. Projetos
        projs = ProjetoService.obter_todos()
        self.lista_projetos_fmt = [f"{p['id']} - {p['nome']}" if p['nome'] else p['id'] for p in projs]
        if not self.lista_projetos_fmt:
            self.lista_projetos_fmt = ["Sem projetos registados"]

        # 2. Materiais
        mats = MaterialService.obter_todos()
        self.lista_materiais_fmt = [f"{m['nome']} - {m['fabricante']}" if m['fabricante'] else m['nome'] for m in mats]
        if not self.lista_materiais_fmt:
            self.lista_materiais_fmt = ["N/A"]

    def construir_layout(self):
        ctk.CTkLabel(self, text=f"Editar Pedido #{PedidoService.formatar_codigo(self.pedido.get('id'))}", font=theme.font_display(18), text_color=theme.ACCENT).pack(pady=(15, 5))

        # --- CABEÇALHO DO PEDIDO ---
        frm_master = ctk.CTkFrame(self, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        frm_master.pack(fill="x", padx=20, pady=10)

        # Linha 1
        ctk.CTkLabel(frm_master, text="REQUERENTE (EMAIL)", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).grid(row=0, column=0, padx=10, pady=(15, 5), sticky="w")
        self.ent_req = theme.entry(frm_master, width=220)
        self.ent_req.grid(row=0, column=1, padx=10, pady=(15, 5), sticky="w")

        ctk.CTkLabel(frm_master, text="DATA DE ENTREGA", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).grid(row=0, column=2, padx=10, pady=(15, 5), sticky="w")
        self.ent_data = theme.entry(frm_master, width=150, font=theme.font_mono(12))
        self.ent_data.grid(row=0, column=3, padx=10, pady=(15, 5), sticky="w")

        # Linha 2
        ctk.CTkLabel(frm_master, text="PROJETO (ID - NOME)", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.cmb_proj = theme.combobox(frm_master, values=self.lista_projetos_fmt, width=220, state="readonly")
        self.cmb_proj.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        ctk.CTkLabel(frm_master, text="TECNOLOGIA BASE", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).grid(row=1, column=2, padx=10, pady=5, sticky="w")
        self.cmb_tech = theme.combobox(frm_master, values=["FDM", "SLA", "SLS"], width=150, state="readonly")
        self.cmb_tech.grid(row=1, column=3, padx=10, pady=5, sticky="w")

        # Linha 3
        ctk.CTkLabel(frm_master, text="LINK / PASTA (REDE)", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.ent_link = theme.entry(frm_master, width=490)
        self.ent_link.grid(row=2, column=1, columnspan=3, padx=10, pady=5, sticky="w")

        # Linha 4
        ctk.CTkLabel(frm_master, text="OBSERVAÇÕES", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).grid(row=3, column=0, padx=10, pady=(5, 15), sticky="nw")
        self.txt_obs = ctk.CTkTextbox(frm_master, width=490, height=50, fg_color=theme.SURFACE_ALT, text_color=theme.TEXT, border_color=theme.BORDER, border_width=1)
        self.txt_obs.grid(row=3, column=1, columnspan=3, padx=10, pady=(5, 15), sticky="w")

        # --- GRELHA DINÂMICA DE PEÇAS ---
        frm_titulo_pecas = ctk.CTkFrame(self, fg_color="transparent")
        frm_titulo_pecas.pack(fill="x", padx=20, pady=(10, 0))

        ctk.CTkLabel(frm_titulo_pecas, text="Lista de Peças a Fabricar", font=theme.font_body(13, "bold"), text_color=theme.ACCENT).pack(side="left")
        theme.button_action(frm_titulo_pecas, text="+ Adicionar Peça", width=120, height=28, command=self.adicionar_linha_peca).pack(side="right")

        self.frm_scroll_pecas = ctk.CTkScrollableFrame(self, fg_color=theme.SURFACE_ALT, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_M, height=220)
        self.frm_scroll_pecas.pack(fill="x", padx=20, pady=5)

        # --- BOTÃO GUARDAR ---
        self.btn_salvar = theme.button_primary(self, text="GUARDAR ALTERAÇÕES", font=theme.font_body(13, "bold"), command=self.salvar_alteracoes, height=45)
        self.btn_salvar.pack(fill="x", padx=20, pady=20)

    def preencher_dados_existentes(self):
        self.ent_req.insert(0, self.pedido.get("requerente_email", self.pedido.get("requerente", "")))
        self.ent_data.insert(0, self.pedido.get("data_entrega", ""))
        self.ent_link.insert(0, self.pedido.get("link_arquivos", ""))
        
        if self.pedido.get("observacoes"):
            self.txt_obs.insert("1.0", self.pedido.get("observacoes"))
            
        self.cmb_tech.set(self.pedido.get("tecnologia", "FDM"))

        # Preenche o Projeto
        nr_p = self.pedido.get("nr_projeto", self.pedido.get("projeto", ""))
        nome_p = self.pedido.get("nome_projeto", "")
        fmt = f"{nr_p} - {nome_p}" if nome_p else str(nr_p)
        if fmt in self.lista_projetos_fmt:
            self.cmb_proj.set(fmt)
        elif self.lista_projetos_fmt:
            self.cmb_proj.set(self.lista_projetos_fmt[0])

        # Preenche as peças existentes
        pecas = self.pedido.get("pecas", [])
        if pecas:
            for p in pecas:
                self.adicionar_linha_peca(pn=p.get("pn", ""), mat=p.get("material", ""), qtd=p.get("qtd_solicitada", 1))
        else:
            self.adicionar_linha_peca()

    def adicionar_linha_peca(self, pn="", mat="", qtd=""):
        linha_frm = ctk.CTkFrame(self.frm_scroll_pecas, fg_color="transparent")
        linha_frm.pack(fill="x", pady=3)

        ent_pn = theme.entry(linha_frm, placeholder_text="Part Number", width=300)
        ent_pn.insert(0, pn)
        ent_pn.pack(side="left", padx=(5, 10))

        cmb_mat = theme.combobox(linha_frm, values=self.lista_materiais_fmt, width=220, state="readonly")
        if mat in self.lista_materiais_fmt:
            cmb_mat.set(mat)
        cmb_mat.pack(side="left", padx=(0, 10))

        ent_qtd = theme.entry(linha_frm, placeholder_text="Qtd", width=70, font=theme.font_mono(12))
        ent_qtd.insert(0, str(qtd))
        ent_qtd.pack(side="left", padx=(0, 10))

        btn_remover = theme.button_danger(linha_frm, text="X", width=30, command=lambda f=linha_frm: self.remover_linha(f))
        btn_remover.pack(side="left")

        self.linhas_pecas.append({"frame": linha_frm, "pn": ent_pn, "mat": cmb_mat, "qtd": ent_qtd})

    def remover_linha(self, frame_alvo):
        frame_alvo.destroy()
        self.linhas_pecas = [linha for linha in self.linhas_pecas if linha["frame"] != frame_alvo]

    def salvar_alteracoes(self):
        req = self.ent_req.get().strip()
        proj_sel = self.cmb_proj.get()
        data_ent = self.ent_data.get().strip()
        link = self.ent_link.get().strip()
        tech = self.cmb_tech.get()
        obs = self.txt_obs.get("1.0", tk.END).strip()

        if not req or not data_ent or proj_sel == "Sem projetos registados":
            messagebox.showerror("Erro", "Requerente, Projeto e Data de Entrega são obrigatórios.")
            return

        if len(self.linhas_pecas) == 0:
            messagebox.showerror("Erro", "O pedido deve conter pelo menos uma peça.")
            return

        if " - " in proj_sel:
            partes = proj_sel.split(" - ", 1)
            nr_proj, nome_proj = partes[0], partes[1]
        else:
            nr_proj, nome_proj = proj_sel, ""

        lista_pecas = []
        for linha in self.linhas_pecas:
            pn = linha["pn"].get().strip()
            mat_peca = linha["mat"].get()
            qtd_str = linha["qtd"].get().strip()
            
            if not pn or not qtd_str:
                messagebox.showerror("Erro", "Todas as peças listadas devem ter PN e Quantidade preenchidos.")
                return
            
            if not qtd_str.isdigit() or int(qtd_str) <= 0:
                messagebox.showerror("Erro", f"A quantidade da peça '{pn}' tem de ser um número inteiro válido.")
                return
                
            lista_pecas.append({
                "pn": pn,
                "material": mat_peca,
                "qtd_solicitada": int(qtd_str),
                "qtd_produzida": 0
            })

        pedido_atualizado = dict(self.pedido)
        pedido_atualizado.update({
            "requerente_email": req,
            "nr_projeto": nr_proj,
            "nome_projeto": nome_proj,
            "tecnologia": tech,
            "observacoes": obs,
            "data_entrega": data_ent,
            "link_arquivos": link,
            "pecas": lista_pecas,
        })
        PedidoService.atualizar_pedido(pedido_atualizado)

        # Trilha de auditoria: regista o que mudou nesta edição — antes,
        # uma correção posterior ao pedido (ex: mudar data de entrega ou
        # requerente) não deixava nenhum rasto de quem alterou o quê.
        AuditService.registrar_diferencas(
            entidade="pedido",
            id_entidade=self.pedido.get("id"),
            dados_antigos=self._dados_antes_da_edicao,
            dados_novos=pedido_atualizado,
            campos_relevantes=[
                "requerente_email", "nr_projeto", "nome_projeto", "tecnologia",
                "data_entrega", "link_arquivos", "observacoes", "pecas",
            ],
        )

        messagebox.showinfo("Sucesso", "Pedido atualizado com sucesso!")
        self.callback_atualizar()
        self.destroy()