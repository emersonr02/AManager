import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import os
from datetime import datetime
from services.producao_service import ProducaoService
from services.pedido_service import PedidoService
from services.nc_service import NCService
from gui import theme

class JanelaFecharOrdem(ctk.CTkToplevel):
    def __init__(self, parent, log_data, callback_salvar):
        super().__init__(parent)
        self.log = log_data
        self.callback_salvar = callback_salvar

        codigo_ordem = ProducaoService.formatar_codigo(self.log.get('id', ''))
        self.title(f"Tratamento e Fecho - Ordem #{codigo_ordem}")

        # Janela mais larga, com o corpo do formulário dentro de uma área
        # scrollável. O nº de checkboxes de ações corretivas varia consoante
        # o código NC escolhido — em vez de a janela crescer (e o botão de
        # gravar sair do ecrã), o cabeçalho e o rodapé (botão + assinatura)
        # ficam sempre fixos na mesma posição; só o meio faz scroll.
        self.geometry("640x760")
        self.minsize(600, 500)
        self.configure(fg_color=theme.BG)
        self.resizable(False, True)  # permite esticar em altura se o ecrã do utilizador for pequeno

        self.transient(parent)
        self.grab_set()

        self.extrair_dados_dinamicos()
        self.construir_layout()

    def extrair_dados_dinamicos(self):
        pedidos_db = PedidoService.obter_todos()
        vinculos = self.log.get("pedidos_vinculados", [])
        
        materiais_set = set()
        
        # 1. Formatar os IDs dos pedidos (Substituindo o Projeto)
        if vinculos:
            self.pedidos_fmt = ", ".join(PedidoService.formatar_codigo(v) for v in vinculos)
            
            # Aproveitar para extrair materiais diretamente dos pedidos vinculados
            for p in pedidos_db:
                if p.get("id") in vinculos:
                    for peca in p.get("pecas", []):
                        if peca.get("material"): materiais_set.add(peca["material"])
        else:
            self.pedidos_fmt = "Nenhum vínculo direto"

        self.material_fmt = " | ".join(materiais_set) if materiais_set else self.log.get("material", "N/A")
        
        # 2. Dados Base
        self.maquina = self.log.get("maquina") or self.log.get("id_maquina", "N/A")
        self.tecnologia = self.log.get("tecnologia", "FDM")
        self.tempo_est = (
            self.log.get("tempo_estimado") or
            self.log.get("hora_maquina") or   # compatibilidade legacy
            self.log.get("tempo") or
            "00:00"
        )
        self.responsavel = self.log.get("operador") or self.log.get("responsavel", "N/A")
        
        # 3. Lógica de Quantidades e SLS
        if self.tecnologia == "SLS":
            try:
                # Tratamento para aceitar tanto vírgula quanto ponto no input
                altura_str = str(self.log.get("altura_cuba", 0)).replace(',', '.')
                perc_str = str(self.log.get("percentagem_po_novo", 0)).replace(',', '.')
                
                altura = float(altura_str)
                perc_novo = float(perc_str)
                
                # Se o operador digitar "30" em vez de "0.3", ajustamos matematicamente
                if perc_novo > 1:
                    perc_novo = perc_novo / 100

                # Fórmula Oficial em ProducaoService.calcular_consumo_sls (retorna Kg).
                # Se o teu painel exibe e abate stock em Gramas (g), deves multiplicar o resultado por 1000.
                consumo_estimado = ProducaoService.calcular_consumo_sls(altura, perc_novo)

                self.qtd_est = f"{consumo_estimado:.2f} (Calc. SLS)"
                self.qtd_raw = consumo_estimado
            except ValueError:
                self.qtd_est = "Erro no Cálculo"
                self.qtd_raw = 0.0
        else:
            # Compatibilidade legacy: "quantidade" era o nome antigo de "quantidade_consumida"
            self.qtd_raw = (
                self.log.get("quantidade_consumida") or
                self.log.get("quantidade") or
                0.0
            )
            self.qtd_est = str(self.qtd_raw)

    def construir_layout(self):
        codigo_ordem = ProducaoService.formatar_codigo(self.log.get('id', ''))

        # --- RODAPÉ FIXO ---
        # Empacotado em primeiro lugar com side="bottom" para reservar o
        # espaço antes de tudo o resto — garante que o botão de gravar
        # nunca é empurrado para fora do ecrã, independentemente de quantos
        # checkboxes de ações corretivas aparecerem no meio.
        frm_rodape = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=0,
                                  border_width=1, border_color=theme.BORDER)
        frm_rodape.pack(side="bottom", fill="x")

        verificador_atual = os.environ.get("USERNAME", "Desconhecido")
        ctk.CTkLabel(frm_rodape, text=f"Este fecho fica registado como verificado por: {verificador_atual}",
                     font=theme.font_body(10), text_color=theme.TEXT_MUTED
                     ).pack(anchor="w", padx=20, pady=(12, 4))

        self.btn_salvar = theme.button_primary(frm_rodape, text="SALVAR APONTAMENTO E FECHAR",
                                                font=theme.font_body(12, "bold"), height=45,
                                                command=self.salvar)
        self.btn_salvar.pack(fill="x", padx=20, pady=(0, 16))

        # --- CABEÇALHO FIXO ---
        ctk.CTkLabel(self, text=f"Tratamento e Fecho - Ordem #{codigo_ordem}",
                     font=theme.font_display(16), text_color=theme.ACCENT
                     ).pack(side="top", pady=(20, 10))

        # --- CORPO SCROLLÁVEL ---
        # Tudo o que pode crescer (resumo, apontamento, checklist, ações
        # corretivas dinâmicas) vive aqui dentro. Se não couber no espaço
        # visível, o utilizador desliza — mas o botão de gravar continua
        # sempre acessível no rodapé, sem precisar de scroll.
        corpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        corpo.pack(side="top", fill="both", expand=True, padx=0, pady=0)

        # --- RESUMO DO PLANEAMENTO ---
        frm_resumo = ctk.CTkFrame(corpo, fg_color=theme.SURFACE_ALT, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        frm_resumo.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(frm_resumo, text="RESUMO DO PLANEAMENTO", font=theme.font_eyebrow(10), text_color=theme.TEAL).pack(anchor="w", padx=15, pady=(10, 5))

        # Agora apresenta os Pedidos em vez do Projeto
        info_texto = f"Máquina: {self.maquina} | Pedidos: {self.pedidos_fmt}\nMaterial: {self.material_fmt} | Tecnologia: {self.tecnologia}\nTempo Est.: {self.tempo_est} | Qtd Est.: {self.qtd_est} g/ml\nResponsável: {self.responsavel}"
        ctk.CTkLabel(frm_resumo, text=info_texto, font=theme.font_mono(11), text_color=theme.TEXT, justify="left").pack(anchor="w", padx=15, pady=(0, 10))

        # --- APONTAMENTO REAL ---
        frm_real = ctk.CTkFrame(corpo, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        frm_real.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(frm_real, text="Apontamento Real de Produção", font=theme.font_body(12, "bold"), text_color=theme.ACCENT).pack(anchor="w", padx=15, pady=(10, 10))

        # Tempo Real
        frm_tr = ctk.CTkFrame(frm_real, fg_color="transparent")
        frm_tr.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(frm_tr, text="Tempo Real (HH:MM):", font=theme.font_body(11), text_color=theme.TEXT_MUTED, width=140, anchor="e").pack(side="left", padx=(0, 10))
        self.ent_tempo_real = theme.entry(frm_tr, width=150, font=theme.font_mono(12))

        t_real_gravado = self.log.get("tempo_real", "")
        self.ent_tempo_real.insert(0, t_real_gravado if t_real_gravado else str(self.tempo_est))
        self.ent_tempo_real.pack(side="left")

        # Quantidade Real
        frm_qr = ctk.CTkFrame(frm_real, fg_color="transparent")
        frm_qr.pack(fill="x", padx=15, pady=(5, 15))
        ctk.CTkLabel(frm_qr, text="Quantidade Real (g/ml):", font=theme.font_body(11), text_color=theme.TEXT_MUTED, width=140, anchor="e").pack(side="left", padx=(0, 10))
        self.ent_qtd_real = theme.entry(frm_qr, width=150, font=theme.font_mono(12))

        q_real_gravado = self.log.get("quantidade_real", "")
        try:
            val_inserir = str(round(float(q_real_gravado), 2)) if q_real_gravado else str(round(float(self.qtd_raw), 2))
            self.ent_qtd_real.insert(0, val_inserir)
        except (ValueError, TypeError):
            self.ent_qtd_real.insert(0, str(q_real_gravado if q_real_gravado else self.qtd_raw))

        self.ent_qtd_real.pack(side="left")

        # --- ESTADO FINAL ---
        ctk.CTkLabel(corpo, text="ESTADO FINAL DA ORDEM", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).pack(anchor="w", padx=20, pady=(15, 5))
        self.cmb_estado = theme.combobox(corpo, values=["Concluída", "Cancelada", "Em Andamento"], width=580, state="readonly")

        # Agora reflete o estado real da ordem (não assume mais que está concluída)
        estado_atual = self.log.get("estado", "Em Andamento")
        if estado_atual == "A Imprimir": estado_atual = "Em Andamento"
        self.cmb_estado.set(estado_atual)
        self.cmb_estado.pack(padx=20, pady=5)

        # --- CRITÉRIOS DE ACEITAÇÃO ---
        frm_cq = ctk.CTkFrame(corpo, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        frm_cq.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(frm_cq, text="CRITÉRIOS DE ACEITAÇÃO (CONTROLO DE QUALIDADE)", font=theme.font_eyebrow(9), text_color=theme.TEXT_MUTED).pack(anchor="w", padx=15, pady=(10, 5))

        frm_checks = ctk.CTkFrame(frm_cq, fg_color="transparent")
        frm_checks.pack(fill="x", padx=15, pady=(5, 10))

        qa_data = self.log.get("controlo_qualidade", {})
        checkbox_kwargs = dict(fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, checkmark_color=theme.WHITE, border_color=theme.TEXT_MUTED, text_color=theme.TEXT)

        # Agora iniciam desmarcados, obrigando à verificação ativa (ou assumem o valor se já foi gravado antes)
        self.chk_visual = ctk.CTkCheckBox(frm_checks, text="Inspeção\nVisual", font=theme.font_body(11), **checkbox_kwargs)
        self.chk_visual.pack(side="left", expand=True)
        if qa_data.get("inspecao_visual"): self.chk_visual.select()
        else: self.chk_visual.deselect()

        self.chk_dimens = ctk.CTkCheckBox(frm_checks, text="Controlo\nDimensional", font=theme.font_body(11), **checkbox_kwargs)
        self.chk_dimens.pack(side="left", expand=True)
        if qa_data.get("controlo_dimensional"): self.chk_dimens.select()
        else: self.chk_dimens.deselect()

        self.chk_conform = ctk.CTkCheckBox(frm_checks, text="Conformidade\ndas Peças", font=theme.font_body(11), **checkbox_kwargs)
        self.chk_conform.pack(side="left", expand=True)
        if qa_data.get("conformidade"): self.chk_conform.select()
        else: self.chk_conform.deselect()

        # --- NÃO-CONFORMIDADE (OPCIONAL) ---
        frm_nc = ctk.CTkFrame(corpo, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        frm_nc.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkLabel(frm_nc, text="NÃO-CONFORMIDADE (SE APLICÁVEL)", font=theme.font_eyebrow(9), text_color=theme.TEXT_MUTED).pack(anchor="w", padx=15, pady=(10, 5))

        valores_nc = ["Nenhuma"] + NCService.obter_nc_por_tecnologia(self.tecnologia)
        self.cmb_nc = theme.combobox(frm_nc, values=valores_nc, width=580, state="readonly", command=self.on_nc_selecionada)
        self.cmb_nc.pack(padx=15, pady=(0, 5), anchor="w")

        # Container onde as ações corretivas sugeridas são renderizadas como
        # checkboxes — permite ao operador confirmar quais foram de facto
        # aplicadas, em vez de apenas listar sugestões que ninguém confirma.
        # Mesmo que este bloco cresça bastante, o corpo scrollável absorve
        # o crescimento sem afetar a posição do botão de gravar.
        self.lbl_acoes_titulo = ctk.CTkLabel(frm_nc, text="", font=theme.font_body(10, "bold"),
                                             text_color=theme.TEXT_MUTED, justify="left")
        self.lbl_acoes_titulo.pack(anchor="w", padx=15, pady=(4, 0))

        self.frm_acoes_check = ctk.CTkFrame(frm_nc, fg_color="transparent")
        self.frm_acoes_check.pack(fill="x", padx=15, pady=(2, 5))
        self._acao_vars: dict[str, tk.BooleanVar] = {}

        self.ent_notas_acao = theme.entry(frm_nc, width=580, font=theme.font_body(10),
                                          placeholder_text="Notas adicionais sobre a correção (opcional)")

        nc_gravado = self.log.get("nc_codigo", "")
        valor_inicial = next((v for v in valores_nc if v.startswith(f"{nc_gravado} -")), "Nenhuma") if nc_gravado else "Nenhuma"
        self.cmb_nc.set(valor_inicial)
        self.on_nc_selecionada(valor_inicial)

    def on_nc_selecionada(self, valor):
        """Reconstrói os checkboxes de ações corretivas para o código NC
        escolhido. Se a ordem já tinha sido fechada antes com este mesmo
        código, restaura quais ações estavam marcadas como aplicadas."""
        # Limpa checkboxes anteriores
        for w in self.frm_acoes_check.winfo_children():
            w.destroy()
        self._acao_vars = {}

        if not valor or valor == "Nenhuma":
            self.lbl_acoes_titulo.configure(text="")
            self.ent_notas_acao.pack_forget()
            return

        cod = valor.split(" - ", 1)[0]
        acoes = NCService.obter_acoes_por_cod(cod)

        if not acoes:
            self.lbl_acoes_titulo.configure(text="Sem ações corretivas associadas a este código.")
            self.ent_notas_acao.pack(padx=15, pady=(0, 10), anchor="w")
            return

        self.lbl_acoes_titulo.configure(
            text="Ações corretivas sugeridas — marca as que foram aplicadas:")

        # Restaura seleção anterior apenas se o código NC não mudou desde
        # o último fecho (evita "herdar" marcações de um problema diferente)
        aplicadas_anteriores = (
            self.log.get("acoes_aplicadas", [])
            if self.log.get("nc_codigo") == cod else []
        )

        checkbox_kwargs = dict(fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                               checkmark_color=theme.WHITE, border_color=theme.TEXT_MUTED,
                               text_color=theme.TEXT)
        for acao in acoes:
            act_cod = acao.get("act", "")
            var = tk.BooleanVar(value=act_cod in aplicadas_anteriores)
            chk = ctk.CTkCheckBox(self.frm_acoes_check, text=acao.get("acao", act_cod),
                                  font=theme.font_body(10), variable=var, **checkbox_kwargs)
            chk.pack(anchor="w", pady=2)
            self._acao_vars[act_cod] = var

        self.ent_notas_acao.pack(padx=15, pady=(4, 10), anchor="w")
        notas_gravadas = self.log.get("notas_acao_corretiva", "")
        if notas_gravadas and self.log.get("nc_codigo") == cod:
            self.ent_notas_acao.delete(0, "end")
            self.ent_notas_acao.insert(0, notas_gravadas)

    def salvar(self):
        t_real = self.ent_tempo_real.get().strip()
        q_real = self.ent_qtd_real.get().strip()
        est_final = self.cmb_estado.get()

        if not t_real or not q_real:
            messagebox.showerror("Erro", "Preencha o Tempo Real e a Quantidade Real antes de fechar a ordem.")
            return

        if not ProducaoService.validar_formato_tempo(t_real):
            messagebox.showerror("Erro de Formato", "O Tempo Real deve estar no formato HH:MM (ex: 02:30).")
            return

        if not ProducaoService.validar_numero_positivo(q_real):
            messagebox.showerror("Erro de Formato", "A Quantidade Real deve ser um número positivo válido.")
            return

        # Impede fechar a ordem se a qualidade não estiver aprovada (Opcional: podes remover este bloco se for permitido fechar sem os 3 checks)
        if est_final == "Concluída" and not (self.chk_visual.get() and self.chk_dimens.get() and self.chk_conform.get()):
            if not messagebox.askyesno("Aviso de Qualidade", "Atenção: Os critérios de aceitação não estão todos validados.\nDesejas concluir a ordem mesmo assim?"):
                return

        self.log["tempo_real"] = t_real
        self.log["quantidade_real"] = q_real
        self.log["estado"] = est_final

        # Rasto de auditoria: quem validou o QA e quando — distinto de
        # "operador", que é quem lançou o fabrico e pode ser outra pessoa.
        self.log["verificado_por"] = os.environ.get("USERNAME", "Desconhecido")
        self.log["data_fecho"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.log["controlo_qualidade"] = {
            "inspecao_visual": self.chk_visual.get() == 1,
            "controlo_dimensional": self.chk_dimens.get() == 1,
            "conformidade": self.chk_conform.get() == 1
        }

        nc_sel = self.cmb_nc.get()
        self.log["nc_codigo"] = nc_sel.split(" - ", 1)[0] if nc_sel and nc_sel != "Nenhuma" else ""

        # Fecha o loop CAPA: grava quais ações corretivas sugeridas foram
        # de facto aplicadas, e notas livres do operador sobre a correção.
        # Sem NC selecionada, os campos ficam vazios — não há o que fechar.
        if self.log["nc_codigo"]:
            self.log["acoes_aplicadas"] = [
                act_cod for act_cod, var in self._acao_vars.items() if var.get()
            ]
            self.log["notas_acao_corretiva"] = self.ent_notas_acao.get().strip()
        else:
            self.log["acoes_aplicadas"] = []
            self.log["notas_acao_corretiva"] = ""

        self.callback_salvar(self.log)
        self.destroy()
