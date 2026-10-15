import os
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk

from services.producao_service import ProducaoService
from services.pedido_service import PedidoService
from services.nc_service import NCService
from services.audit_service import AuditService
from gui import theme

_ESTADOS = ["Concluída", "Cancelada", "Em Andamento"]
_UNIDADE = {"FDM": "g", "SLA": "ml", "SLS": "kg"}


class JanelaFecharOrdem(theme.Dialogo):
    """Fecho de uma ordem de produção, com divulgação progressiva:
    1. o estado final vem primeiro e decide o que se pede a seguir;
    2. Concluída → controlo de qualidade por peça (com "Aprovar todas");
    3. Cancelada → a não-conformidade passa a obrigatória (sem ela o Pareto
       de NCs subestimava as falhas)."""

    def __init__(self, parent, log_data, callback_salvar):
        self.log = log_data
        # Cópia do estado original — alimenta a trilha de auditoria quando a
        # ordem já tinha sido fechada antes e está a ser reaberta/corrigida.
        self._dados_antes_da_edicao = dict(log_data)
        self.callback_salvar = callback_salvar
        self.extrair_dados_dinamicos()

        codigo = ProducaoService.formatar_codigo(self.log.get("id", ""))
        super().__init__(parent, f"Fechar ordem {codigo}", largura=700, altura=780, texto_acao="Guardar fecho",
                         subtitulo=f"{self.maquina}  ·  {self.tecnologia}  ·  pedidos {self.pedidos_fmt}")
        self.btn_salvar = self.btn_acao
        self.rodape_info.configure(text=f"Fica registado como verificado por {os.environ.get('USERNAME', 'Desconhecido')}")
        self.construir_layout()

    # ------------------------------------------------------------------ #
    #  DADOS                                                               #
    # ------------------------------------------------------------------ #
    def extrair_dados_dinamicos(self):
        pedidos_db = PedidoService.obter_todos()
        vinculos = self.log.get("pedidos_vinculados", [])

        materiais_set = set()
        qa_gravado = self.log.get("qa_por_peca", {})
        self.linhas_qa_dados = []

        if vinculos:
            self.pedidos_fmt = ", ".join(PedidoService.formatar_codigo(v) for v in vinculos)
            for p in pedidos_db:
                if p.get("id") in vinculos:
                    for idx, peca in enumerate(p.get("pecas", [])):
                        if peca.get("material"):
                            materiais_set.add(peca["material"])
                        # O índice entra na chave porque um pedido pode ter PNs
                        # repetidos — sem ele, duas linhas colidiriam na mesma entrada.
                        chave = f"{p['id']}:{peca.get('pn', '')}:{idx}"
                        self.linhas_qa_dados.append({
                            "chave": chave,
                            "pedido_id": p["id"],
                            "pn": peca.get("pn", ""),
                            "material": peca.get("material", ""),
                            "qtd": peca.get("qtd_solicitada", ""),
                            "gravado": qa_gravado.get(chave, {}),
                        })
        else:
            self.pedidos_fmt = "Nenhum vínculo direto"

        self.material_fmt = " | ".join(materiais_set) if materiais_set else self.log.get("material", "N/A")
        self.maquina = self.log.get("maquina") or self.log.get("id_maquina", "N/A")
        self.tecnologia = self.log.get("tecnologia", "FDM")
        self.unidade = _UNIDADE.get(self.tecnologia, "g")
        self.tempo_est = (
            self.log.get("tempo_estimado") or
            self.log.get("hora_maquina") or   # compatibilidade legacy
            self.log.get("tempo") or
            "00:00"
        )
        self.responsavel = self.log.get("operador") or self.log.get("responsavel", "N/A")

        if self.tecnologia == "SLS":
            try:
                altura = float(str(self.log.get("altura_cuba", 0)).replace(",", "."))
                perc_novo = float(str(self.log.get("percentagem_po_novo", 0)).replace(",", "."))
                if perc_novo > 1:  # "30" escrito em vez de "0.3"
                    perc_novo = perc_novo / 100
                consumo_estimado = ProducaoService.calcular_consumo_sls(altura, perc_novo)
                self.qtd_est = f"{consumo_estimado:.2f}"
                self.qtd_raw = consumo_estimado
            except ValueError:
                self.qtd_est = "erro no cálculo"
                self.qtd_raw = 0.0
        else:
            # Compatibilidade legacy: "quantidade" era o nome antigo de "quantidade_consumida"
            self.qtd_raw = (
                self.log.get("quantidade_consumida") or
                self.log.get("quantidade") or
                0.0
            )
            self.qtd_est = str(self.qtd_raw)

    # ------------------------------------------------------------------ #
    #  LAYOUT                                                              #
    # ------------------------------------------------------------------ #
    def construir_layout(self):
        corpo = ctk.CTkFrame(self.corpo, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=12)

        # 1. Planeamento — grelha rótulo/valor (antes um bloco de texto com "|")
        plan = theme.secao(corpo, "Planeamento")
        dados = [
            ("Pedidos", self.pedidos_fmt), ("Material", self.material_fmt),
            ("Tempo estimado", self.tempo_est), ("Quantidade estimada", f"{self.qtd_est} {self.unidade}"),
            ("Lançada por", self.responsavel), ("Início", self.log.get("data_inicio", "—")),
        ]
        for i, (rot, val) in enumerate(dados):
            ctk.CTkLabel(plan, text=rot, font=theme.font_body(12), text_color=theme.TEXT_MUTED, anchor="w").grid(
                row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 10), pady=2)
            ctk.CTkLabel(plan, text=str(val), font=theme.font_body(12, "bold"), text_color=theme.TEXT, anchor="w",
                         wraplength=210, justify="left").grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w", padx=(0, 24), pady=2)

        # 2. Estado final — decide o resto do formulário
        est = theme.secao(corpo, "Estado final")
        self.cmb_estado = theme.segmented(est, values=_ESTADOS, command=self._ao_mudar_estado)
        estado_atual = self.log.get("estado", "Em Andamento")
        if estado_atual == "A Imprimir":
            estado_atual = "Em Andamento"
        self.cmb_estado.set(estado_atual if estado_atual in _ESTADOS else "Em Andamento")
        self.cmb_estado.pack(anchor="w")

        # 3. Apontamento real
        real = theme.secao(corpo, "Apontamento real")
        ctk.CTkLabel(real, text="Tempo real (HH:MM)", font=theme.font_body(12), text_color=theme.TEXT_MUTED).grid(row=0, column=0, sticky="w")
        self.ent_tempo_real = theme.entry(real, width=150, font=theme.font_mono(12))
        t_real_gravado = self.log.get("tempo_real", "")
        self.ent_tempo_real.insert(0, t_real_gravado if t_real_gravado else str(self.tempo_est))
        self.ent_tempo_real.grid(row=1, column=0, sticky="w", padx=(0, 24))

        ctk.CTkLabel(real, text=f"Quantidade real ({self.unidade})", font=theme.font_body(12), text_color=theme.TEXT_MUTED).grid(row=0, column=1, sticky="w")
        self.ent_qtd_real = theme.entry(real, width=150, font=theme.font_mono(12))
        q_real_gravado = self.log.get("quantidade_real", "")
        try:
            val_inserir = str(round(float(q_real_gravado), 2)) if q_real_gravado else str(round(float(self.qtd_raw), 2))
        except (ValueError, TypeError):
            val_inserir = str(q_real_gravado if q_real_gravado else self.qtd_raw)
        self.ent_qtd_real.insert(0, val_inserir)
        self.ent_qtd_real.grid(row=1, column=1, sticky="w")

        # 4. Controlo de qualidade por peça (só para Concluída)
        self.frm_cq_card = theme.card(corpo)
        cab = ctk.CTkFrame(self.frm_cq_card, fg_color="transparent")
        cab.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(cab, text="CONTROLO DE QUALIDADE POR PEÇA", font=theme.font_eyebrow(11),
                     text_color=theme.TEXT_MUTED).pack(side="left")
        self.linhas_qa = []
        frm_cq = ctk.CTkFrame(self.frm_cq_card, fg_color="transparent")
        frm_cq.pack(fill="x", padx=16, pady=(0, 12))

        if not self.linhas_qa_dados:
            ctk.CTkLabel(frm_cq, text="Sem peças associadas a esta ordem.", font=theme.font_body(12),
                         text_color=theme.TEXT_MUTED).pack(anchor="w")
        else:
            theme.button_ghost(cab, text="Aprovar todas", height=28, width=120,
                               command=self.aprovar_todas).pack(side="right")
            frm_cq.columnconfigure(0, weight=1)
            for i, peca in enumerate(self.linhas_qa_dados):
                rotulo = f"{PedidoService.formatar_codigo(peca['pedido_id'])} · {peca['pn']}  ({peca['material']}, qtd {peca['qtd']})"
                ctk.CTkLabel(frm_cq, text=rotulo, font=theme.font_body(12), text_color=theme.TEXT, anchor="w",
                             wraplength=300, justify="left").grid(row=i, column=0, sticky="w", pady=3)
                gravado = peca["gravado"]
                v_visual = tk.BooleanVar(value=bool(gravado.get("inspecao_visual")))
                v_dimens = tk.BooleanVar(value=bool(gravado.get("controlo_dimensional")))
                v_conform = tk.BooleanVar(value=bool(gravado.get("conformidade")))
                for col, (texto, var) in enumerate((("Visual", v_visual), ("Dimensional", v_dimens),
                                                     ("Conformidade", v_conform)), start=1):
                    theme.checkbox(frm_cq, text=texto, variable=var, width=1, font=theme.font_body(11)).grid(
                        row=i, column=col, padx=(8, 0), pady=3, sticky="w")
                self.linhas_qa.append({
                    "chave": peca["chave"],
                    "visual": v_visual, "dimensional": v_dimens, "conformidade": v_conform,
                })

        # 5. Não-conformidade (obrigatória se Cancelada)
        frm_nc_card = theme.card(corpo)
        frm_nc_card.pack(fill="x", pady=(0, 12))
        self.lbl_nc_titulo = ctk.CTkLabel(frm_nc_card, text="", font=theme.font_eyebrow(11), text_color=theme.TEXT_MUTED, anchor="w")
        self.lbl_nc_titulo.pack(fill="x", padx=16, pady=(12, 4))
        frm_nc = ctk.CTkFrame(frm_nc_card, fg_color="transparent")
        frm_nc.pack(fill="x", padx=16, pady=(0, 12))

        self.valores_nc = ["Nenhuma"] + NCService.obter_nc_por_tecnologia(self.tecnologia)
        self.cmb_nc = theme.combobox(frm_nc, values=self.valores_nc, state="readonly", command=self.on_nc_selecionada)
        self.cmb_nc.pack(fill="x")

        # Ações corretivas sugeridas para o código escolhido, como checkboxes — o
        # operador confirma quais foram de facto aplicadas (fecho do ciclo CAPA).
        self.lbl_acoes_titulo = ctk.CTkLabel(frm_nc, text="", font=theme.font_body(12, "bold"),
                                             text_color=theme.TEXT_MUTED, justify="left")
        self.lbl_acoes_titulo.pack(anchor="w", pady=(8, 0))
        self.frm_acoes_check = ctk.CTkFrame(frm_nc, fg_color="transparent")
        self.frm_acoes_check.pack(fill="x", pady=(2, 4))
        self._acao_vars: dict[str, tk.BooleanVar] = {}
        self.ent_notas_acao = theme.entry(frm_nc, font=theme.font_body(12),
                                          placeholder_text="Notas sobre a correção (opcional)")

        nc_gravado = self.log.get("nc_codigo", "")
        valor_inicial = next((v for v in self.valores_nc if v.startswith(f"{nc_gravado} -")), "Nenhuma") if nc_gravado else "Nenhuma"
        self.cmb_nc.set(valor_inicial)
        self.on_nc_selecionada(valor_inicial)

        self._frm_nc_card = frm_nc_card
        self._ao_mudar_estado(self.cmb_estado.get())

    def _ao_mudar_estado(self, estado):
        """Mostra o controlo de qualidade só para Concluída; marca a NC como
        obrigatória para Cancelada."""
        if estado == "Concluída":
            self.frm_cq_card.pack(fill="x", pady=(0, 12), before=self._frm_nc_card)
        else:
            self.frm_cq_card.pack_forget()
        obrigatoria = estado == "Cancelada" and len(self.valores_nc) > 1
        self.lbl_nc_titulo.configure(
            text="NÃO-CONFORMIDADE *  (obrigatória ao cancelar)" if obrigatoria else "NÃO-CONFORMIDADE (SE APLICÁVEL)",
            text_color=theme.CRITICAL if obrigatoria else theme.TEXT_MUTED)

    def aprovar_todas(self):
        for v in self.linhas_qa:
            v["visual"].set(True)
            v["dimensional"].set(True)
            v["conformidade"].set(True)

    def on_nc_selecionada(self, valor):
        """Reconstrói os checkboxes de ações corretivas para o código NC
        escolhido. Se a ordem já tinha sido fechada antes com este mesmo
        código, restaura quais ações estavam marcadas como aplicadas."""
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
            self.ent_notas_acao.pack(fill="x", pady=(4, 0))
            return

        self.lbl_acoes_titulo.configure(text="Ações corretivas sugeridas — marque as que foram aplicadas:")
        # Restaura a seleção anterior só se o código NC não mudou desde o último
        # fecho (evita "herdar" marcações de um problema diferente)
        aplicadas_anteriores = self.log.get("acoes_aplicadas", []) if self.log.get("nc_codigo") == cod else []
        for acao in acoes:
            act_cod = acao.get("act", "")
            var = tk.BooleanVar(value=act_cod in aplicadas_anteriores)
            theme.checkbox(self.frm_acoes_check, text=acao.get("acao", act_cod), variable=var,
                           font=theme.font_body(12)).pack(anchor="w", pady=2)
            self._acao_vars[act_cod] = var

        self.ent_notas_acao.pack(fill="x", pady=(4, 0))
        notas_gravadas = self.log.get("notas_acao_corretiva", "")
        if notas_gravadas and self.log.get("nc_codigo") == cod:
            self.ent_notas_acao.delete(0, "end")
            self.ent_notas_acao.insert(0, notas_gravadas)

    # ------------------------------------------------------------------ #
    #  GRAVAR                                                              #
    # ------------------------------------------------------------------ #
    def confirmar(self):
        self.salvar()

    def salvar(self):
        t_real = self.ent_tempo_real.get().strip()
        q_real = self.ent_qtd_real.get().strip()
        est_final = self.cmb_estado.get()
        nc_sel = self.cmb_nc.get()

        erros = []
        if not t_real or not ProducaoService.validar_formato_tempo(t_real):
            erros.append("Tempo real no formato HH:MM (ex: 02:30).")
        if not q_real or not ProducaoService.validar_numero_positivo(q_real):
            erros.append("Quantidade real: um número maior que zero.")
        if est_final == "Cancelada" and len(self.valores_nc) > 1 and (not nc_sel or nc_sel == "Nenhuma"):
            erros.append("Indique a não-conformidade que levou ao cancelamento.")
        if erros:
            messagebox.showerror("Fecho incompleto", "Corrija antes de guardar:\n\n" + "\n".join(f"• {e}" for e in erros))
            return

        # Concluir com peças sem os 3 critérios aprovados pede confirmação.
        # all([]) é True — uma ordem sem peças vinculadas não bloqueia.
        todas_completas = all(
            v["visual"].get() and v["dimensional"].get() and v["conformidade"].get()
            for v in self.linhas_qa
        )
        if est_final == "Concluída" and not todas_completas:
            if not messagebox.askyesno("Controlo de qualidade incompleto",
                                       "Nem todas as peças têm os critérios de aceitação validados.\n"
                                       "Concluir a ordem mesmo assim?"):
                return

        self.log["tempo_real"] = t_real
        self.log["quantidade_real"] = q_real
        self.log["estado"] = est_final

        # Rasto de auditoria: quem validou o QA e quando — distinto de
        # "operador", que é quem lançou o fabrico e pode ser outra pessoa.
        self.log["verificado_por"] = os.environ.get("USERNAME", "Desconhecido")
        self.log["data_fecho"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.log["qa_por_peca"] = {
            v["chave"]: {
                "inspecao_visual": v["visual"].get(),
                "controlo_dimensional": v["dimensional"].get(),
                "conformidade": v["conformidade"].get(),
            }
            for v in self.linhas_qa
        }
        # Agregado derivado do detalhe por peça — cada critério só é "Sim" se
        # TODAS as peças passaram nesse critério (mantém o export de auditoria,
        # que lê "controlo_qualidade", coerente com o detalhe por peça).
        self.log["controlo_qualidade"] = {
            "inspecao_visual": all(v["visual"].get() for v in self.linhas_qa),
            "controlo_dimensional": all(v["dimensional"].get() for v in self.linhas_qa),
            "conformidade": all(v["conformidade"].get() for v in self.linhas_qa),
        } if self.linhas_qa else {}

        self.log["nc_codigo"] = nc_sel.split(" - ", 1)[0] if nc_sel and nc_sel != "Nenhuma" else ""

        # Fecha o loop CAPA: grava quais ações corretivas sugeridas foram de
        # facto aplicadas, e notas livres do operador sobre a correção.
        if self.log["nc_codigo"]:
            self.log["acoes_aplicadas"] = [act_cod for act_cod, var in self._acao_vars.items() if var.get()]
            self.log["notas_acao_corretiva"] = self.ent_notas_acao.get().strip()
        else:
            self.log["acoes_aplicadas"] = []
            self.log["notas_acao_corretiva"] = ""

        # Trilha de auditoria: se esta ordem já tinha sido fechada antes
        # (reabertura para correção), regista o que mudou desde o último fecho.
        if self._dados_antes_da_edicao.get("verificado_por"):
            AuditService.registrar_diferencas(
                entidade="producao",
                id_entidade=self.log.get("id"),
                dados_antigos=self._dados_antes_da_edicao,
                dados_novos=self.log,
                campos_relevantes=["estado", "tempo_real", "quantidade_real", "nc_codigo", "acoes_aplicadas"],
            )

        self.callback_salvar(self.log)
        self.destroy()
