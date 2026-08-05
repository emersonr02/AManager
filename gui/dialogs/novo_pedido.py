import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import re
import os

from config.paths import ARQUIVO_PEDIDOS
from database.json_manager import JSONManager
from services.pedido_service import PedidoService
from services.projeto_service import ProjetoService
from services.material_service import MaterialService
from gui import theme

# Modelo de email esperado por processar_texto_email — mantido em sincronia com
# docs/modelo_pedido_email.md. Ver esse ficheiro para a explicação de cada campo.
MODELO_EMAIL = """TAREFA: <descrição curta do que é pedido>
PROJETO: <número - nome, tem de bater certo com um projeto já registado>
RESPONSÁVEL: <nome de quem acompanha o projeto>
REQUERENTE: <email de quem pede>
LINK FICHEIROS: <caminho de rede ou link para os ficheiros>
PRAZO DE ENTREGA: DD/MM/AAAA
CRITÉRIOS DE ACEITAÇÃO: <tolerâncias, acabamento, etc.>
OBSERVAÇÕES: Tecnologia: FDM|SLA|SLS; Material: <nome do material>; <notas livres>
LISTA DE PEÇAS: <PN1>; <Material1>; <Qtd1> <PN2>; <Material2>; <Qtd2> ...

Exemplo:

TAREFA: Fabrico de peças para protótipo
PROJETO: 257147 - PPS AquaFountain
RESPONSÁVEL: Ana Moura
REQUERENTE: joao.silva@ceiia.com
LINK FICHEIROS: \\\\ceiia.com\\PPS\\AquaFountain
PRAZO DE ENTREGA: 20/09/2026
CRITÉRIOS DE ACEITAÇÃO: Tolerância dimensional ±0.2mm
OBSERVAÇÕES: Tecnologia: FDM; Material: PETG Preto; Entregar em saco individual por peça.
LISTA DE PEÇAS: AQF-001-Base; PETG Preto; 10 AQF-002-Tampa; PETG Preto; 5

Notas: o Requerente nunca é lido automaticamente (escolha sempre manual).
Tecnologia e Material ficam dentro de OBSERVAÇÕES, não são chaves de topo.
LISTA DE PEÇAS usa só ";" como separador, nunca "|"."""


class JanelaNovoPedido(ctk.CTkToplevel):
    def __init__(self, parent, callback_atualizar):
        super().__init__(parent)
        self.callback_atualizar = callback_atualizar

        self.title("Criar Novo Pedido de Produção")
        self.geometry("820x820")
        self.configure(fg_color=theme.BG)
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()

        self.linhas_pecas = [] 
        self.carregar_dados_auxiliares()
        self.construir_layout()

    def obter_requerentes_historico(self):
        if not os.path.exists(ARQUIVO_PEDIDOS): return []
        pedidos = JSONManager.carregar(ARQUIVO_PEDIDOS)
        requerentes = {p.get("requerente_email", "").strip() for p in pedidos}
        return sorted([req for req in requerentes if req])

    def carregar_dados_auxiliares(self):
        projs = ProjetoService.obter_todos()
        self.lista_projetos_fmt = [f"{p['id']} - {p['nome']}" if p['nome'] else p['id'] for p in projs]
        if not self.lista_projetos_fmt: self.lista_projetos_fmt = ["Sem projetos registados"]

        mats = MaterialService.obter_todos()
        self.lista_materiais_fmt = [f"{m['nome']} - {m['fabricante']}" if m['fabricante'] else m['nome'] for m in mats]
        if not self.lista_materiais_fmt: self.lista_materiais_fmt = ["N/A"]

    def construir_layout(self):
        # --- CABEÇALHO COM BOTÃO DE IMPORTAÇÃO ---
        frm_topo = ctk.CTkFrame(self, fg_color="transparent")
        frm_topo.pack(fill="x", padx=20, pady=(15, 5))

        ctk.CTkLabel(frm_topo, text="Criar Novo Pedido", font=theme.font_display(18), text_color=theme.ACCENT).pack(side="left")
        theme.button_ghost(frm_topo, text="📥 Importar de Email", command=self.abrir_importacao_email).pack(side="right")

        # --- 1. CABEÇALHO DO PEDIDO (MASTER) ---
        frm_master = ctk.CTkFrame(self, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        frm_master.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(frm_master, text="REQUERENTE (EMAIL)", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).grid(row=0, column=0, padx=10, pady=(15, 5), sticky="w")
        lista_requerentes = self.obter_requerentes_historico()
        valores_combo = lista_requerentes if lista_requerentes else [""]
        self.cmb_req = theme.combobox(frm_master, values=valores_combo, width=220)
        self.cmb_req.grid(row=0, column=1, padx=10, pady=(15, 5), sticky="w")
        self.cmb_req.set("")

        ctk.CTkLabel(frm_master, text="DATA DE ENTREGA", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).grid(row=0, column=2, padx=10, pady=(15, 5), sticky="w")
        self.ent_data = theme.entry(frm_master, width=150, placeholder_text="AAAA-MM-DD", font=theme.font_mono(12))
        self.ent_data.grid(row=0, column=3, padx=10, pady=(15, 5), sticky="w")

        ctk.CTkLabel(frm_master, text="PROJETO (NR - NOME)", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.cmb_proj = theme.combobox(frm_master, values=self.lista_projetos_fmt, width=220, state="readonly")
        self.cmb_proj.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        ctk.CTkLabel(frm_master, text="TECNOLOGIA BASE", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).grid(row=1, column=2, padx=10, pady=5, sticky="w")
        self.cmb_tech = theme.combobox(frm_master, values=["FDM", "SLA", "SLS"], width=150, state="readonly")
        self.cmb_tech.grid(row=1, column=3, padx=10, pady=5, sticky="w")

        ctk.CTkLabel(frm_master, text="LINK / PASTA (REDE)", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.ent_link = theme.entry(frm_master, width=490)
        self.ent_link.grid(row=2, column=1, columnspan=3, padx=10, pady=5, sticky="w")

        ctk.CTkLabel(frm_master, text="OBSERVAÇÕES", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).grid(row=3, column=0, padx=10, pady=(5, 15), sticky="nw")
        self.txt_obs = ctk.CTkTextbox(frm_master, width=490, height=50, fg_color=theme.SURFACE_ALT, text_color=theme.TEXT, border_color=theme.BORDER, border_width=1)
        self.txt_obs.grid(row=3, column=1, columnspan=3, padx=10, pady=(5, 15), sticky="w")

        # --- 2. GRELHA DINÂMICA DE PEÇAS ---
        frm_titulo_pecas = ctk.CTkFrame(self, fg_color="transparent")
        frm_titulo_pecas.pack(fill="x", padx=20, pady=(10, 0))

        ctk.CTkLabel(frm_titulo_pecas, text="Lista de Peças a Fabricar", font=theme.font_body(13, "bold"), text_color=theme.ACCENT).pack(side="left")
        theme.button_action(frm_titulo_pecas, text="+ Adicionar Peça", width=120, height=28, command=self.adicionar_linha_peca).pack(side="right")

        self.frm_scroll_pecas = ctk.CTkScrollableFrame(self, fg_color=theme.SURFACE_ALT, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_M, height=220)
        self.frm_scroll_pecas.pack(fill="x", padx=20, pady=5)
        self.adicionar_linha_peca()

        self.btn_salvar = theme.button_primary(self, text="REGISTAR NOVO PEDIDO", font=theme.font_body(13, "bold"), command=self.salvar_pedido, height=45)
        self.btn_salvar.pack(fill="x", padx=20, pady=20)

    def abrir_importacao_email(self):
        top_email = ctk.CTkToplevel(self)
        top_email.title("Importar Email")
        top_email.geometry("500x430")
        top_email.configure(fg_color=theme.BG)
        top_email.transient(self)
        top_email.grab_set()

        frm_topo = ctk.CTkFrame(top_email, fg_color="transparent")
        frm_topo.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(frm_topo, text="Cole aqui o texto do email:", font=theme.font_body(12, "bold"), text_color=theme.TEXT).pack(side="left")
        theme.button_ghost(frm_topo, text="Ver Modelo", command=self.mostrar_modelo_email).pack(side="right")

        txt_email = ctk.CTkTextbox(top_email, width=460, height=250, fg_color=theme.SURFACE_ALT, text_color=theme.TEXT, border_color=theme.BORDER, border_width=1)
        txt_email.pack(padx=20, pady=5)

        def processar_e_fechar():
            texto = txt_email.get("1.0", tk.END)
            self.processar_texto_email(texto)
            top_email.destroy()

        theme.button_primary(top_email, text="Processar Texto", command=processar_e_fechar).pack(pady=15)

    def mostrar_modelo_email(self):
        top_modelo = ctk.CTkToplevel(self)
        top_modelo.title("Modelo de Email Esperado")
        top_modelo.geometry("560x520")
        top_modelo.configure(fg_color=theme.BG)
        top_modelo.transient(self)
        top_modelo.grab_set()

        ctk.CTkLabel(top_modelo, text="Modelo de Email Esperado", font=theme.font_display(15), text_color=theme.ACCENT).pack(pady=(15, 5), padx=20, anchor="w")
        ctk.CTkLabel(top_modelo, text="Copie e distribua a quem faz pedidos por email.", font=theme.font_body(11), text_color=theme.TEXT_MUTED).pack(padx=20, anchor="w")

        txt_modelo = ctk.CTkTextbox(top_modelo, width=520, height=390, fg_color=theme.SURFACE_ALT, text_color=theme.TEXT, font=theme.font_mono(11), border_color=theme.BORDER, border_width=1)
        txt_modelo.pack(padx=20, pady=10, fill="both", expand=True)
        txt_modelo.insert("1.0", MODELO_EMAIL)
        txt_modelo.configure(state="disabled")

        theme.button_ghost(top_modelo, text="Fechar", command=top_modelo.destroy).pack(pady=(0, 15))

    def processar_texto_email(self, texto):
        """ Motor de leitura blindado contra texto esmagado e sem quebras de linha """
        # 1. PARSER ROBUSTO (Corta o texto onde encontra as chaves, mesmo sem Enters)
        padrao_chaves = r"(?i)(TAREFA:|PROJETO:|RESPONSÁVEL:|REQUERENTE:|LINK FICHEIROS:|CRITÉRIOS DE ACEITAÇÃO:|PRAZO DE ENTREGA:|OBSERVAÇÕES:|LISTA DE PEÇAS:)"
        partes_texto = re.split(padrao_chaves, texto)
        
        dados = {}
        chave_atual = None
        
        for parte in partes_texto:
            parte_limpa = parte.strip()
            if not parte_limpa: continue
            
            if re.match(padrao_chaves, parte_limpa):
                chave_atual = parte_limpa.upper().replace(':', '')
                dados[chave_atual] = ""
            elif chave_atual:
                dados[chave_atual] += parte_limpa + " "

        # --- 1. REQUERENTE (Mantém-se Manual) ---
        self.cmb_req.set("")

        # --- 2. LINK E INFERÊNCIA DO PART NUMBER ---
        link = dados.get("LINK FICHEIROS", "").strip()
        pn_inferido = ""
        if link: 
            self.ent_link.delete(0, 'end')
            self.ent_link.insert(0, link)
            pn_inferido = link.replace('/', '\\').split('\\')[-1]

        # --- 3. PROJETO (Tenta adivinhar cruzando as palavras do link) ---
        projeto_extraido = dados.get("PROJETO", "").strip()
        projeto_encontrado = False
        
        if projeto_extraido:
            for p_fmt in self.lista_projetos_fmt:
                if projeto_extraido.lower() in p_fmt.lower():
                    self.cmb_proj.set(p_fmt)
                    projeto_encontrado = True
                    break
                    
        if not projeto_encontrado and link:
            for p_fmt in self.lista_projetos_fmt:
                if p_fmt == "Sem projetos registados": continue
                nome_proj_limpo = p_fmt.split(" - ")[-1]
                palavras_chave = [p.lower() for p in nome_proj_limpo.split() if len(p) > 3]
                for palavra in palavras_chave:
                    if palavra in link.lower():
                        self.cmb_proj.set(p_fmt)
                        projeto_encontrado = True
                        break
                if projeto_encontrado: break

        # --- 4. PRAZO DE ENTREGA ---
        prazo = dados.get("PRAZO DE ENTREGA", "").strip()
        if prazo:
            try:
                data_obj = datetime.strptime(prazo, "%d/%m/%Y")
                self.ent_data.delete(0, 'end')
                self.ent_data.insert(0, data_obj.strftime("%Y-%m-%d"))
            except ValueError:
                self.ent_data.delete(0, 'end')
                self.ent_data.insert(0, prazo)

        # --- 5 & 6. OBSERVAÇÕES E TECNOLOGIA ---
        obs_brutas = dados.get("OBSERVAÇÕES", "").strip()
        crit = dados.get("CRITÉRIOS DE ACEITAÇÃO", "").strip()
        
        obs_upper = obs_brutas.upper()
        if "SLS" in obs_upper: self.cmb_tech.set("SLS")
        elif "FDM" in obs_upper: self.cmb_tech.set("FDM")
        elif "SLA" in obs_upper: self.cmb_tech.set("SLA")

        obs_brutas = obs_brutas.replace("Email:", "").strip()
        partes_obs = [p.strip() for p in obs_brutas.replace('\n', ';').split(';') if p.strip()]
        obs_restantes = []
        material_inferido = ""
        
        for parte in partes_obs:
            parte_lower = parte.lower()
            if parte_lower.startswith("tecnologia"):
                continue 
            elif parte_lower.startswith("material"):
                if ":" in parte: material_inferido = parte.split(":", 1)[1].strip()
                continue 
            else:
                obs_restantes.append(parte)

        obs_final = ""
        if crit: obs_final += f"Critérios de Aceitação: {crit}\n"
        if obs_restantes: obs_final += "; ".join(obs_restantes)
            
        if obs_final:
            self.txt_obs.delete("1.0", 'end')
            self.txt_obs.insert("1.0", obs_final.strip())

        # --- 7. PROCESSAR LISTA DE PEÇAS (Algoritmo Limpo) ---
        texto_pecas = dados.get("LISTA DE PEÇAS", "").strip()
        
        if texto_pecas:
            for linha in self.linhas_pecas:
                linha["frame"].destroy()
            self.linhas_pecas = []
            
            segmentos = [s.strip() for s in texto_pecas.split(';') if s.strip()]
            
            pn_atual = segmentos[0] if len(segmentos) > 0 else "S/N"
            idx = 1
            
            while idx < len(segmentos):
                mat_atual = segmentos[idx]
                qtd_raw = segmentos[idx+1] if (idx + 1) < len(segmentos) else "1"
                
                match_qtd = re.match(r'^(\d+)\s*(.*)$', qtd_raw)
                if match_qtd:
                    qtd_atual = match_qtd.group(1)
                    pn_proximo = match_qtd.group(2).strip()
                else:
                    qtd_atual = "1"
                    pn_proximo = qtd_raw.strip()

                self.adicionar_linha_peca()
                l_atual = self.linhas_pecas[-1]
                
                l_atual["pn"].delete(0, 'end')
                l_atual["pn"].insert(0, pn_atual)
                
                l_atual["qtd"].delete(0, 'end')
                l_atual["qtd"].insert(0, qtd_atual)
                
                match_mat = False
                for m_fmt in self.lista_materiais_fmt:
                    if mat_atual.lower() in m_fmt.lower():
                        l_atual["mat"].set(m_fmt)
                        match_mat = True
                        break
                if not match_mat:
                    l_atual["mat"].set(mat_atual)

                pn_atual = pn_proximo
                idx += 2
                
                if not pn_atual and idx < len(segmentos):
                    pn_atual = segmentos[idx]
                    idx += 1

        # --- 8. FALLBACK (Se não tiver "LISTA DE PEÇAS", tenta usar PN único) ---
        elif material_inferido or pn_inferido:
            if not self.linhas_pecas:
                self.adicionar_linha_peca()
            
            linha = self.linhas_pecas[0]
            if pn_inferido:
                linha["pn"].delete(0, 'end')
                linha["pn"].insert(0, pn_inferido)
                
            linha["qtd"].delete(0, 'end')
            linha["qtd"].insert(0, "1")

            if material_inferido:
                match_mat = False
                for m_fmt in self.lista_materiais_fmt:
                    if material_inferido.lower() in m_fmt.lower():
                        linha["mat"].set(m_fmt)
                        match_mat = True
                        break
                if not match_mat:
                    linha["mat"].set(material_inferido)

    def adicionar_linha_peca(self):
        linha_frm = ctk.CTkFrame(self.frm_scroll_pecas, fg_color="transparent")
        linha_frm.pack(fill="x", pady=3)
        ent_pn = theme.entry(linha_frm, placeholder_text="Part Number (Ex: AQF-001)", width=280)
        ent_pn.pack(side="left", padx=(5, 10))
        cmb_mat = theme.combobox(linha_frm, values=self.lista_materiais_fmt, width=220, state="readonly")
        cmb_mat.pack(side="left", padx=(0, 10))
        ent_qtd = theme.entry(linha_frm, placeholder_text="Qtd", width=70, font=theme.font_mono(12))
        ent_qtd.pack(side="left", padx=(0, 10))
        btn_remover = theme.button_danger(linha_frm, text="X", width=30, command=lambda f=linha_frm: self.remover_linha(f))
        btn_remover.pack(side="left")
        self.linhas_pecas.append({"frame": linha_frm, "pn": ent_pn, "mat": cmb_mat, "qtd": ent_qtd})

    def remover_linha(self, frame_alvo):
        frame_alvo.destroy()
        self.linhas_pecas = [linha for linha in self.linhas_pecas if linha["frame"] != frame_alvo]

    def salvar_pedido(self):
        req = self.cmb_req.get().strip()
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
                
            lista_pecas.append({"pn": pn, "material": mat_peca, "qtd_solicitada": int(qtd_str), "qtd_produzida": 0})

        PedidoService.criar_pedido(
            requerente_email=req,
            nr_projeto=nr_proj,
            nome_projeto=nome_proj,
            tecnologia=tech,
            data_entrega=data_ent,
            link_arquivos=link,
            observacoes=obs,
            pecas=lista_pecas
        )
        messagebox.showinfo("Sucesso", "Pedido registado com sucesso!")
        self.callback_atualizar()
        self.destroy()