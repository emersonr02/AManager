import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

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

_SEM_PROJETOS = "Sem projetos registados"
_SEM_MATERIAIS = "N/A"


def mensagem_erros_pedido(erros, sem_projetos, sem_materiais):
    """Junta os erros de validação numa só mensagem (em vez de um popup por
    campo) e acrescenta onde resolver quando o problema é não haver projetos
    ou materiais registados."""
    linhas = ["Corrija antes de gravar:", ""] + [f"• {e}" for e in erros]
    if sem_projetos or sem_materiais:
        linhas += ["", "Projetos e materiais registam-se em Configuração → Projetos / Materiais."]
    return "\n".join(linhas)


class FormularioPedido(theme.Dialogo):
    """Base partilhada por Novo e Editar Pedido (antes eram dois ficheiros quase
    iguais, com regras de validação que já tinham divergido)."""

    def __init__(self, parent, titulo, texto_acao, callback_atualizar):
        self.callback_atualizar = callback_atualizar
        self.linhas_pecas = []
        self.carregar_dados_auxiliares()
        # Um único scroll para o formulário inteiro (a lista de peças já não tem
        # scroll próprio): num portátil a lista ficava espremida a zero.
        super().__init__(parent, titulo, largura=880, altura=780, texto_acao=texto_acao, scroll=True,
                         subtitulo="Campos com * são obrigatórios.")
        self.btn_salvar = self.btn_acao
        self.construir_layout()

    # ------------------------------------------------------------------ #
    def carregar_dados_auxiliares(self):
        projs = ProjetoService.obter_todos()
        self.lista_projetos_fmt = [f"{p['id']} - {p['nome']}" if p['nome'] else p['id'] for p in projs]
        if not self.lista_projetos_fmt:
            self.lista_projetos_fmt = [_SEM_PROJETOS]

        mats = MaterialService.obter_todos()
        self.lista_materiais_fmt = [f"{m['nome']} - {m['fabricante']}" if m['fabricante'] else m['nome'] for m in mats]
        if not self.lista_materiais_fmt:
            self.lista_materiais_fmt = [_SEM_MATERIAIS]

    def _criar_campo_requerente(self, parent):
        """Novo Pedido usa uma lista dos requerentes anteriores; Editar usa um campo livre."""
        raise NotImplementedError

    def construir_layout(self):
        base = ctk.CTkFrame(self.corpo, fg_color="transparent")
        base.pack(fill="both", expand=True, padx=12)
        frm_master = theme.card(base)
        frm_master.pack(fill="x", pady=(0, 12))
        frm_master.columnconfigure(1, weight=1)
        frm_master.columnconfigure(3, weight=1)

        def _rotulo(texto, linha, coluna, obrigatorio=False, sticky="w"):
            theme.rotulo_campo(frm_master, texto, obrigatorio).grid(row=linha, column=coluna, padx=(14, 8), pady=(10, 2), sticky=sticky)

        _rotulo("Requerente (email)", 0, 0, True)
        self._criar_campo_requerente(frm_master).grid(row=1, column=0, columnspan=2, padx=(14, 8), sticky="ew")

        _rotulo("Data de entrega", 0, 2, True)
        self.ent_data = theme.entry(frm_master, placeholder_text="DD/MM/AAAA", font=theme.font_mono(12))
        self.ent_data.grid(row=1, column=2, columnspan=2, padx=(14, 14), sticky="ew")

        _rotulo("Projeto (nº - nome)", 2, 0, True)
        self.cmb_proj = theme.combobox(frm_master, values=self.lista_projetos_fmt, state="readonly")
        self.cmb_proj.grid(row=3, column=0, columnspan=2, padx=(14, 8), sticky="ew")

        _rotulo("Tecnologia", 2, 2, True)
        self.cmb_tech = theme.combobox(frm_master, values=list(PedidoService.TECNOLOGIAS), state="readonly")
        self.cmb_tech.grid(row=3, column=2, columnspan=2, padx=(14, 14), sticky="ew")

        _rotulo("Link / pasta de rede", 4, 0)
        self.ent_link = theme.entry(frm_master)
        self.ent_link.grid(row=5, column=0, columnspan=4, padx=14, sticky="ew")

        _rotulo("Observações", 6, 0)
        self.txt_obs = ctk.CTkTextbox(frm_master, height=54, fg_color=theme.SURFACE_ALT, text_color=theme.TEXT,
                                      border_color=theme.BORDER, border_width=1, font=theme.font_body(13))
        self.txt_obs.grid(row=7, column=0, columnspan=4, padx=14, pady=(0, 14), sticky="ew")

        # --- PEÇAS ---
        frm_titulo_pecas = ctk.CTkFrame(base, fg_color="transparent")
        frm_titulo_pecas.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(frm_titulo_pecas, text="Peças a fabricar *", font=theme.font_body(14, "bold"),
                     text_color=theme.TEXT).pack(side="left")
        theme.button_ghost(frm_titulo_pecas, text="+ Adicionar peça", width=130, height=30,
                           command=self.adicionar_linha_peca).pack(side="right")

        # Cabeçalhos de coluna da lista de peças (antes as linhas não tinham rótulo)
        frm_cab = ctk.CTkFrame(base, fg_color="transparent")
        frm_cab.pack(fill="x", padx=12)
        for texto, largura in (("Part number", 300), ("Material", 230), ("Qtd", 70)):
            ctk.CTkLabel(frm_cab, text=texto.upper(), width=largura, anchor="w", font=theme.font_eyebrow(11),
                         text_color=theme.TEXT_MUTED).pack(side="left", padx=(0, 10))

        self.frm_scroll_pecas = ctk.CTkFrame(base, fg_color=theme.SURFACE_ALT, border_width=1,
                                             border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        self.frm_scroll_pecas.pack(fill="x", pady=(0, 4))
        self.preencher()

    def preencher(self):
        """Estado inicial do formulário (Novo: uma linha vazia; Editar: os dados do pedido)."""
        self.adicionar_linha_peca()

    def adicionar_linha_peca(self, pn="", mat="", qtd="", qtd_produzida=0):
        linha_frm = ctk.CTkFrame(self.frm_scroll_pecas, fg_color="transparent")
        linha_frm.pack(fill="x", padx=6, pady=4)
        ent_pn = theme.entry(linha_frm, placeholder_text="ex.: AQF-001", width=300)
        if pn:
            ent_pn.insert(0, pn)
        ent_pn.pack(side="left", padx=(4, 10))

        cmb_mat = theme.combobox(linha_frm, values=self.lista_materiais_fmt, width=230, state="readonly")
        if mat in self.lista_materiais_fmt:
            cmb_mat.set(mat)
        elif mat:
            # Material legado/desativado: mantém-no em vez de deixar o campo vazio
            # (o material é obrigatório e isso impediria gravar o pedido).
            cmb_mat.configure(values=[mat] + [m for m in self.lista_materiais_fmt if m != _SEM_MATERIAIS])
            cmb_mat.set(mat)
        cmb_mat.pack(side="left", padx=(0, 10))

        ent_qtd = theme.entry(linha_frm, placeholder_text="0", width=70, font=theme.font_mono(12))
        if qtd != "":
            ent_qtd.insert(0, str(qtd))
        ent_qtd.pack(side="left", padx=(0, 10))

        btn_remover = theme.button_secondary(linha_frm, text="Remover", width=80,
                                             command=lambda f=linha_frm: self.remover_linha(f))
        btn_remover.pack(side="left")
        self.linhas_pecas.append({"frame": linha_frm, "pn": ent_pn, "mat": cmb_mat, "qtd": ent_qtd,
                                  "qtd_produzida": qtd_produzida})

    def remover_linha(self, frame_alvo):
        frame_alvo.destroy()
        self.linhas_pecas = [linha for linha in self.linhas_pecas if linha["frame"] != frame_alvo]

    # ------------------------------------------------------------------ #
    def _ler_e_validar(self, requerente):
        """Lê o formulário e valida-o. Devolve o dicionário de campos, ou None
        (depois de mostrar TODOS os erros numa só mensagem)."""
        proj_sel = self.cmb_proj.get()
        if proj_sel == _SEM_PROJETOS:
            proj_sel = ""
        pecas_ui = [{
            "pn": linha["pn"].get().strip(),
            "material": "" if linha["mat"].get() == _SEM_MATERIAIS else linha["mat"].get(),
            "qtd": linha["qtd"].get().strip(),
            "qtd_produzida": linha.get("qtd_produzida", 0),
        } for linha in self.linhas_pecas]
        tech = self.cmb_tech.get()
        data_ent = self.ent_data.get().strip()

        erros = PedidoService.validar_dados_pedido(requerente, proj_sel, tech, data_ent, pecas_ui)
        if erros:
            messagebox.showerror("Pedido incompleto", mensagem_erros_pedido(
                erros, self.lista_projetos_fmt == [_SEM_PROJETOS], self.lista_materiais_fmt == [_SEM_MATERIAIS]))
            return None

        nr_proj, nome_proj = (proj_sel.split(" - ", 1) + [""])[:2] if " - " in proj_sel else (proj_sel, "")
        return {
            "requerente_email": requerente,
            "nr_projeto": nr_proj,
            "nome_projeto": nome_proj,
            "tecnologia": tech,
            "data_entrega": PedidoService.normalizar_data_entrega(data_ent),
            "link_arquivos": self.ent_link.get().strip(),
            "observacoes": self.txt_obs.get("1.0", tk.END).strip(),
            "pecas": [{
                "pn": p["pn"],
                "material": p["material"],
                "qtd_solicitada": int(p["qtd"]),
                # mantém o que já foi produzido (fecho de ordens), limitado ao pedido
                "qtd_produzida": min(int(p["qtd_produzida"] or 0), int(p["qtd"])),
            } for p in pecas_ui],
        }


class JanelaNovoPedido(FormularioPedido):
    def __init__(self, parent, callback_atualizar):
        super().__init__(parent, "Novo pedido", "Registar pedido", callback_atualizar)
        theme.button_ghost(self.cabecalho_acoes, text="Importar de email", height=32,
                           command=self.abrir_importacao_email).pack()

    def obter_requerentes_historico(self):
        pedidos = PedidoService.obter_todos()
        requerentes = {p.get("requerente_email", "").strip() for p in pedidos}
        return sorted(r for r in requerentes if r)

    def _criar_campo_requerente(self, parent):
        lista = self.obter_requerentes_historico()
        self.cmb_req = theme.combobox(parent, values=lista if lista else [""])
        self.cmb_req.set("")
        return self.cmb_req

    def abrir_importacao_email(self):
        JanelaImportarEmail(self, self.processar_texto_email)

    def processar_texto_email(self, texto):
        """Delega o parsing para PedidoService.importar_de_email e aplica
        os resultados na UI — mantém toda a lógica de negócio fora da vista."""
        resultado = PedidoService.importar_de_email(texto, self.lista_projetos_fmt, self.lista_materiais_fmt)

        proj_fmt = (f"{resultado['nr_projeto']} - {resultado['nome_projeto']}"
                    if resultado['nome_projeto'] else resultado['nr_projeto'])
        if proj_fmt and proj_fmt in self.lista_projetos_fmt:
            self.cmb_proj.set(proj_fmt)
        if resultado["tecnologia"]:
            self.cmb_tech.set(resultado["tecnologia"])
        if resultado["data_entrega"]:
            self.ent_data.delete(0, "end")
            self.ent_data.insert(0, resultado["data_entrega"])
        if resultado["link_arquivos"]:
            self.ent_link.delete(0, "end")
            self.ent_link.insert(0, resultado["link_arquivos"])
        if resultado["observacoes"]:
            self.txt_obs.delete("1.0", "end")
            self.txt_obs.insert("1.0", resultado["observacoes"])
        if resultado["pecas"]:
            for linha in self.linhas_pecas:
                linha["frame"].destroy()
            self.linhas_pecas = []
            for peca in resultado["pecas"]:
                self.adicionar_linha_peca(pn=peca["pn"], qtd=peca["qtd"])
                self.linhas_pecas[-1]["mat"].set(peca["material"])

    def confirmar(self):
        self.salvar_pedido()

    def salvar_pedido(self):
        dados = self._ler_e_validar(self.cmb_req.get().strip())
        if dados is None:
            return
        novo_pedido = PedidoService.criar_pedido(
            requerente_email=dados["requerente_email"], nr_projeto=dados["nr_projeto"],
            nome_projeto=dados["nome_projeto"], tecnologia=dados["tecnologia"],
            data_entrega=dados["data_entrega"], link_arquivos=dados["link_arquivos"],
            observacoes=dados["observacoes"], pecas=dados["pecas"],
        )
        theme.toast(self, f"Pedido {PedidoService.formatar_codigo(novo_pedido.get('id'))} registado.")
        self.callback_atualizar()
        self.destroy()


class JanelaImportarEmail(theme.Dialogo):
    def __init__(self, parent, ao_processar):
        self._ao_processar = ao_processar
        super().__init__(parent, "Importar pedido de email", largura=560, altura=480, texto_acao="Preencher formulário",
                         scroll=False, subtitulo="Cole o texto do email. Os campos reconhecidos são preenchidos; "
                                                 "o requerente escolhe-se sempre à mão.")
        theme.button_ghost(self.cabecalho_acoes, text="Ver modelo", height=30,
                           command=lambda: JanelaModeloEmail(self)).pack()
        self.txt_email = ctk.CTkTextbox(self.corpo, fg_color=theme.SURFACE, text_color=theme.TEXT,
                                        border_color=theme.BORDER, border_width=1, font=theme.font_body(12))
        self.txt_email.pack(fill="both", expand=True)
        self.txt_email.focus_set()

    def confirmar(self):
        self._ao_processar(self.txt_email.get("1.0", tk.END))
        self.destroy()


class JanelaModeloEmail(theme.Dialogo):
    def __init__(self, parent):
        super().__init__(parent, "Modelo de email para pedidos", largura=600, altura=560, texto_acao="Copiar modelo",
                         scroll=False, subtitulo="Copie e distribua a quem faz pedidos por email.")
        txt = ctk.CTkTextbox(self.corpo, fg_color=theme.SURFACE, text_color=theme.TEXT, font=theme.font_mono(11),
                             border_color=theme.BORDER, border_width=1)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", MODELO_EMAIL)
        txt.configure(state="disabled")

    def confirmar(self):
        self.clipboard_clear()
        self.clipboard_append(MODELO_EMAIL)
        theme.toast(self, "Modelo copiado para a área de transferência.", "info")
        self.destroy()
