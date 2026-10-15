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
_SEM_NC = "Nenhuma"


def _inteiro(texto):
    texto = str(texto).strip()
    return int(texto) if texto.isdigit() else None


def _hhmm(tempo) -> str:
    """Qualquer formato de tempo gravado (HH:MM, H:MM:SS, "N days, H:MM:SS") → HH:MM."""
    return ProducaoService.converter_para_string(ProducaoService.converter_para_horas(str(tempo)))


class JanelaFecharOrdem(theme.Dialogo):
    """Fecho de uma ordem de produção, com divulgação progressiva:
    1. o estado final vem primeiro e decide o que se pede a seguir;
    2. Concluída → resultado POR PEÇA: unidades aprovadas e rejeitadas e a NC
       da peça (às vezes só uma peça falha), mais as inspeções;
    3. Cancelada → a NC da ordem (falha da impressão inteira) é obrigatória."""

    def __init__(self, parent, log_data, callback_salvar):
        self.log = log_data
        # Cópia do estado original — alimenta a trilha de auditoria quando a
        # ordem já tinha sido fechada antes e está a ser reaberta/corrigida.
        self._dados_antes_da_edicao = dict(log_data)
        self.callback_salvar = callback_salvar
        self.extrair_dados_dinamicos()

        codigo = ProducaoService.formatar_codigo(self.log.get("id", ""))
        super().__init__(parent, f"Fechar ordem {codigo}", largura=860, altura=800, texto_acao="Guardar fecho",
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
        qa_gravado = self.log.get("qa_por_peca", {}) or {}

        # Peças desta ordem (as escolhidas no lançamento; em ordens antigas, as
        # peças dos pedidos vinculados) com a quantidade planeada.
        self.linhas_qa_dados = []
        for peca in ProducaoService.pecas_da_producao(self.log, pedidos_db):
            gravado = qa_gravado.get(peca["chave"]) if isinstance(qa_gravado, dict) else None
            self.linhas_qa_dados.append({
                "chave": peca["chave"],
                "pedido_id": peca["pedido_id"],
                "indice": peca.get("indice"),
                "pn": peca["pn"],
                "material": peca["material"],
                "qtd": peca["qtd"],
                "gravado": gravado if isinstance(gravado, dict) else {},
            })

        self.pedidos_fmt = ", ".join(PedidoService.formatar_codigo(v) for v in vinculos) if vinculos else "Nenhum vínculo direto"
        materiais = sorted({p["material"] for p in self.linhas_qa_dados if p["material"]})
        self.material_fmt = " | ".join(materiais) if materiais else self.log.get("material", "N/A")
        self.maquina = self.log.get("maquina") or self.log.get("id_maquina", "N/A")
        self.tecnologia = self.log.get("tecnologia", "FDM")
        self.unidade = _UNIDADE.get(self.tecnologia, "g")
        # Registos antigos guardavam o tempo como "H:MM:SS" ou "1 day, H:MM:SS":
        # mostrado sempre como HH:MM, o formato que o fecho valida.
        self.tempo_est = _hhmm(
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
        self.valores_nc = [_SEM_NC] + NCService.obter_nc_por_tecnologia(self.tecnologia)

        # 1. Planeamento — grelha rótulo/valor
        plan = theme.secao(corpo, "Planeamento")
        dados = [
            ("Pedidos", self.pedidos_fmt), ("Material", self.material_fmt),
            ("Tempo estimado", self.tempo_est), ("Material estimado", f"{self.qtd_est} {self.unidade}"),
            ("Lançada por", self.responsavel), ("Início", self.log.get("data_inicio", "—")),
        ]
        for i, (rot, val) in enumerate(dados):
            ctk.CTkLabel(plan, text=rot, font=theme.font_body(12), text_color=theme.TEXT_MUTED, anchor="w").grid(
                row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 10), pady=2)
            ctk.CTkLabel(plan, text=str(val), font=theme.font_body(12, "bold"), text_color=theme.TEXT, anchor="w",
                         wraplength=260, justify="left").grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w", padx=(0, 24), pady=2)

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
        self.ent_tempo_real.insert(0, _hhmm(t_real_gravado) if t_real_gravado else self.tempo_est)
        self.ent_tempo_real.grid(row=1, column=0, sticky="w", padx=(0, 24))

        ctk.CTkLabel(real, text=f"Material gasto ({self.unidade})", font=theme.font_body(12), text_color=theme.TEXT_MUTED).grid(row=0, column=1, sticky="w")
        self.ent_qtd_real = theme.entry(real, width=150, font=theme.font_mono(12))
        q_real_gravado = self.log.get("quantidade_real", "")
        try:
            val_inserir = str(round(float(q_real_gravado), 2)) if q_real_gravado else str(round(float(self.qtd_raw), 2))
        except (ValueError, TypeError):
            val_inserir = str(q_real_gravado if q_real_gravado else self.qtd_raw)
        self.ent_qtd_real.insert(0, val_inserir)
        self.ent_qtd_real.grid(row=1, column=1, sticky="w")

        # 4. Resultado por peça (só para Concluída)
        self._construir_resultado_por_peca(corpo)

        # 5. NC da ordem (falha da impressão inteira) + ações corretivas
        frm_nc_card = theme.card(corpo)
        frm_nc_card.pack(fill="x", pady=(0, 12))
        self.lbl_nc_titulo = ctk.CTkLabel(frm_nc_card, text="", font=theme.font_eyebrow(11), text_color=theme.TEXT_MUTED, anchor="w")
        self.lbl_nc_titulo.pack(fill="x", padx=16, pady=(12, 4))
        frm_nc = ctk.CTkFrame(frm_nc_card, fg_color="transparent")
        frm_nc.pack(fill="x", padx=16, pady=(0, 12))

        self.cmb_nc = theme.combobox(frm_nc, values=self.valores_nc, state="readonly", command=self.on_nc_selecionada)
        self.cmb_nc.pack(fill="x")

        # Ações corretivas sugeridas para TODOS os códigos em uso (da ordem e das
        # peças), como checkboxes — o operador confirma as aplicadas (CAPA).
        self.lbl_acoes_titulo = ctk.CTkLabel(frm_nc, text="", font=theme.font_body(12, "bold"),
                                             text_color=theme.TEXT_MUTED, justify="left")
        self.lbl_acoes_titulo.pack(anchor="w", pady=(8, 0))
        self.frm_acoes_check = ctk.CTkFrame(frm_nc, fg_color="transparent")
        self.frm_acoes_check.pack(fill="x", pady=(2, 4))
        self._acao_vars: dict[str, tk.BooleanVar] = {}
        self.ent_notas_acao = theme.entry(frm_nc, font=theme.font_body(12),
                                          placeholder_text="Notas sobre a correção (opcional)")

        nc_gravado = self.log.get("nc_codigo", "")
        self.cmb_nc.set(self._valor_nc(nc_gravado))
        self._frm_nc_card = frm_nc_card
        self.on_nc_selecionada(self.cmb_nc.get())
        self._ao_mudar_estado(self.cmb_estado.get())

    def _valor_nc(self, codigo):
        if not codigo:
            return _SEM_NC
        return next((v for v in self.valores_nc if v.startswith(f"{codigo} -")), _SEM_NC)

    def _construir_resultado_por_peca(self, corpo):
        self.frm_cq_card = theme.card(corpo)
        cab = ctk.CTkFrame(self.frm_cq_card, fg_color="transparent")
        cab.pack(fill="x", padx=16, pady=(12, 2))
        ctk.CTkLabel(cab, text="RESULTADO POR PEÇA", font=theme.font_eyebrow(11), text_color=theme.TEXT_MUTED).pack(side="left")
        ctk.CTkLabel(self.frm_cq_card, text="Por cada peça: quantas unidades ficaram aprovadas e quantas rejeitadas "
                                            "(com a NC da peça). Só as aprovadas contam como produzidas no pedido.",
                     font=theme.font_body(11), text_color=theme.TEXT_MUTED, anchor="w", justify="left",
                     wraplength=760).pack(fill="x", padx=16)
        self.linhas_qa = []
        tabela = ctk.CTkFrame(self.frm_cq_card, fg_color="transparent")
        tabela.pack(fill="x", padx=16, pady=(6, 12))

        if not self.linhas_qa_dados:
            ctk.CTkLabel(tabela, text="Sem peças associadas a esta ordem.", font=theme.font_body(12),
                         text_color=theme.TEXT_MUTED).pack(anchor="w")
            return

        theme.button_ghost(cab, text="Aprovar todas", height=28, width=120, command=self.aprovar_todas).pack(side="right")
        tabela.columnconfigure(0, weight=1)
        for col, titulo in enumerate(["Peça", "Plan.", "Aprovadas", "Rejeitadas", "NC da peça", "Inspeção"]):
            ctk.CTkLabel(tabela, text=titulo.upper(), font=theme.font_eyebrow(11), text_color=theme.TEXT_MUTED,
                         anchor="w").grid(row=0, column=col, sticky="w", padx=(0, 8), pady=(0, 4))

        valores_nc_peca = [_SEM_NC] + self.valores_nc[1:]
        for i, peca in enumerate(self.linhas_qa_dados, start=1):
            gravado = peca["gravado"] or {}
            planeado = int(peca["qtd"] or 0)
            rotulo = f"{peca['pn']}\n{PedidoService.formatar_codigo(peca['pedido_id'])} · {peca['material']}"
            ctk.CTkLabel(tabela, text=rotulo, font=theme.font_body(12), text_color=theme.TEXT, anchor="w",
                         wraplength=220, justify="left").grid(row=i, column=0, sticky="w", pady=4, padx=(0, 8))
            ctk.CTkLabel(tabela, text=str(planeado), font=theme.font_mono(12), text_color=theme.TEXT).grid(row=i, column=1, sticky="w", padx=(0, 8))

            if "qtd_aprovada" in gravado:
                aprov, rej, nc_peca = gravado.get("qtd_aprovada", 0), gravado.get("qtd_rejeitada", 0), gravado.get("nc_codigo", "")
            elif gravado.get("conformidade") is False:
                # Fecho de uma versão anterior (só conforme / não conforme):
                # a peça não conforme conta como rejeitada, com a NC da ordem.
                aprov, rej, nc_peca = 0, planeado, self.log.get("nc_codigo", "")
            else:
                aprov, rej, nc_peca = planeado, 0, ""

            ent_aprov = theme.entry(tabela, width=70, font=theme.font_mono(12), justify="right")
            ent_aprov.insert(0, str(aprov))
            ent_aprov.grid(row=i, column=2, sticky="w", padx=(0, 8))
            ent_rej = theme.entry(tabela, width=70, font=theme.font_mono(12), justify="right")
            ent_rej.insert(0, str(rej))
            ent_rej.grid(row=i, column=3, sticky="w", padx=(0, 8))

            cmb_nc = theme.combobox(tabela, values=valores_nc_peca, state="readonly", width=180,
                                    command=lambda _v: self.on_nc_selecionada(self.cmb_nc.get()))
            cmb_nc.set(self._valor_nc(nc_peca))
            cmb_nc.grid(row=i, column=4, sticky="w", padx=(0, 8))

            frm_insp = ctk.CTkFrame(tabela, fg_color="transparent")
            frm_insp.grid(row=i, column=5, sticky="w")
            v_visual = tk.BooleanVar(value=bool(gravado.get("inspecao_visual")))
            v_dimens = tk.BooleanVar(value=bool(gravado.get("controlo_dimensional")))
            theme.checkbox(frm_insp, text="Visual", variable=v_visual, width=1, font=theme.font_body(11)).pack(anchor="w", pady=(0, 3))
            theme.checkbox(frm_insp, text="Dimensional", variable=v_dimens, width=1, font=theme.font_body(11)).pack(anchor="w")

            linha = {"chave": peca["chave"], "pn": peca["pn"], "planeado": planeado,
                     "ent_aprovadas": ent_aprov, "ent_rejeitadas": ent_rej, "cmb_nc": cmb_nc,
                     "visual": v_visual, "dimensional": v_dimens}
            # Escrever as rejeitadas acerta as aprovadas (planeado − rejeitadas)
            ent_rej.bind("<KeyRelease>", lambda e, l=linha: self._acertar_aprovadas(l), add="+")
            self.linhas_qa.append(linha)

    def _acertar_aprovadas(self, linha):
        rej = _inteiro(linha["ent_rejeitadas"].get())
        if rej is None:
            return
        linha["ent_aprovadas"].delete(0, "end")
        linha["ent_aprovadas"].insert(0, str(max(linha["planeado"] - rej, 0)))

    def _ao_mudar_estado(self, estado):
        """Resultado por peça só para Concluída; NC da ordem obrigatória para Cancelada."""
        if estado == "Concluída":
            self.frm_cq_card.pack(fill="x", pady=(0, 12), before=self._frm_nc_card)
        else:
            self.frm_cq_card.pack_forget()
        obrigatoria = estado == "Cancelada" and len(self.valores_nc) > 1
        self.lbl_nc_titulo.configure(
            text="NÃO-CONFORMIDADE DA ORDEM *  (obrigatória ao cancelar)" if obrigatoria
            else "NÃO-CONFORMIDADE DA ORDEM (FALHA DA IMPRESSÃO INTEIRA, SE APLICÁVEL)",
            text_color=theme.CRITICAL if obrigatoria else theme.TEXT_MUTED)

    def aprovar_todas(self):
        for linha in self.linhas_qa:
            linha["visual"].set(True)
            linha["dimensional"].set(True)
            linha["ent_aprovadas"].delete(0, "end")
            linha["ent_aprovadas"].insert(0, str(linha["planeado"]))
            linha["ent_rejeitadas"].delete(0, "end")
            linha["ent_rejeitadas"].insert(0, "0")
            linha["cmb_nc"].set(_SEM_NC)
        self.on_nc_selecionada(self.cmb_nc.get())

    # ------------------------------------------------------------------ #
    #  AÇÕES CORRETIVAS                                                    #
    # ------------------------------------------------------------------ #
    def _codigos_em_uso(self, valor_ordem=None):
        codigos = []
        valores = [valor_ordem if valor_ordem is not None else self.cmb_nc.get()]
        valores += [linha["cmb_nc"].get() for linha in getattr(self, "linhas_qa", [])]
        for valor in valores:
            if valor and valor != _SEM_NC:
                cod = valor.split(" - ", 1)[0]
                if cod not in codigos:
                    codigos.append(cod)
        return codigos

    def on_nc_selecionada(self, valor):
        """Reconstrói os checkboxes de ações corretivas para todos os códigos NC
        em uso (o da ordem e os das peças). Restaura as ações já marcadas num
        fecho anterior, se forem de um código que continua em uso."""
        for w in self.frm_acoes_check.winfo_children():
            w.destroy()
        self._acao_vars = {}

        codigos = self._codigos_em_uso(valor)
        if not codigos:
            self.lbl_acoes_titulo.configure(text="")
            self.ent_notas_acao.pack_forget()
            return

        acoes, vistos = [], set()
        for cod in codigos:
            for acao in NCService.obter_acoes_por_cod(cod):
                chave = acao.get("act") or acao.get("acao")
                if chave not in vistos:
                    vistos.add(chave)
                    acoes.append(acao)

        if not acoes:
            self.lbl_acoes_titulo.configure(text="Sem ações corretivas associadas a " + ", ".join(codigos) + ".")
            self.ent_notas_acao.pack(fill="x", pady=(4, 0))
            return

        self.lbl_acoes_titulo.configure(text=f"Ações corretivas sugeridas ({', '.join(codigos)}) — marque as que foram aplicadas:")
        codigos_anteriores = set(ProducaoService.ncs_da_producao(self.log))
        aplicadas_anteriores = self.log.get("acoes_aplicadas", []) if codigos_anteriores & set(codigos) else []
        for acao in acoes:
            act_cod = acao.get("act", "")
            var = tk.BooleanVar(value=act_cod in aplicadas_anteriores)
            theme.checkbox(self.frm_acoes_check, text=acao.get("acao", act_cod), variable=var,
                           font=theme.font_body(12)).pack(anchor="w", pady=2)
            self._acao_vars[act_cod] = var

        self.ent_notas_acao.pack(fill="x", pady=(4, 0))
        notas_gravadas = self.log.get("notas_acao_corretiva", "")
        if notas_gravadas and aplicadas_anteriores is not None and codigos_anteriores & set(codigos):
            self.ent_notas_acao.delete(0, "end")
            self.ent_notas_acao.insert(0, notas_gravadas)

    # ------------------------------------------------------------------ #
    #  GRAVAR                                                              #
    # ------------------------------------------------------------------ #
    def confirmar(self):
        self.salvar()

    def _ler_resultado_por_peca(self, erros):
        """{chave: registo} a partir da tabela de peças; acrescenta a `erros`
        o que estiver inválido."""
        ha_codigos = len(self.valores_nc) > 1
        resultado = {}
        for linha in self.linhas_qa:
            aprov = _inteiro(linha["ent_aprovadas"].get())
            rej = _inteiro(linha["ent_rejeitadas"].get())
            nome = linha["pn"] or linha["chave"]
            if aprov is None or rej is None:
                erros.append(f"{nome}: aprovadas e rejeitadas têm de ser números inteiros (0 ou mais).")
                continue
            if aprov + rej != linha["planeado"]:
                erros.append(f"{nome}: aprovadas + rejeitadas tem de dar {linha['planeado']} (planeado).")
            nc_val = linha["cmb_nc"].get()
            nc_cod = nc_val.split(" - ", 1)[0] if nc_val and nc_val != _SEM_NC else ""
            if rej > 0 and ha_codigos and not nc_cod:
                erros.append(f"{nome}: indique a NC das {rej} peça(s) rejeitada(s).")
            resultado[linha["chave"]] = {
                "qtd_planeada": linha["planeado"],
                "qtd_aprovada": aprov,
                "qtd_rejeitada": rej,
                "nc_codigo": nc_cod if rej > 0 else "",
                "inspecao_visual": linha["visual"].get(),
                "controlo_dimensional": linha["dimensional"].get(),
                "conformidade": rej == 0 and aprov > 0,
            }
        return resultado

    def salvar(self):
        t_real = self.ent_tempo_real.get().strip()
        q_real = self.ent_qtd_real.get().strip()
        est_final = self.cmb_estado.get()
        nc_sel = self.cmb_nc.get()

        erros = []
        if not t_real or not ProducaoService.validar_formato_tempo(t_real):
            erros.append("Tempo real no formato HH:MM (ex: 02:30).")
        if not q_real or not ProducaoService.validar_numero_positivo(q_real):
            erros.append("Material gasto: um número maior que zero.")
        if est_final == "Cancelada" and len(self.valores_nc) > 1 and (not nc_sel or nc_sel == _SEM_NC):
            erros.append("Indique a não-conformidade que levou ao cancelamento.")
        qa = self._ler_resultado_por_peca(erros) if est_final == "Concluída" else None
        if erros:
            messagebox.showerror("Fecho incompleto", "Corrija antes de guardar:\n\n" + "\n".join(f"• {e}" for e in erros))
            return

        # Peças aprovadas sem as duas inspeções feitas pedem confirmação.
        if qa:
            sem_inspecao = [r for r in qa.values() if r["qtd_aprovada"] and not (r["inspecao_visual"] and r["controlo_dimensional"])]
            if sem_inspecao and not messagebox.askyesno(
                    "Inspeção incompleta",
                    "Há peças aprovadas sem a inspeção visual e dimensional assinaladas.\nConcluir a ordem mesmo assim?"):
                return

        self.log["tempo_real"] = t_real
        self.log["quantidade_real"] = q_real
        self.log["estado"] = est_final

        # Ordens de versões anteriores não guardavam as peças (cobriam pedidos
        # inteiros): grava as que este fecho mostrou, para a ordem deixar de
        # depender do que o pedido tiver produzido depois.
        if not self.log.get("pecas_producao") and self.linhas_qa_dados:
            self.log["pecas_producao"] = [
                {"pedido_id": p["pedido_id"], "indice": p["indice"], "pn": p["pn"],
                 "material": p["material"], "qtd": int(p["qtd"] or 0)}
                for p in self.linhas_qa_dados]

        # Rasto de auditoria: quem validou o QA e quando — distinto de
        # "operador", que é quem lançou o fabrico e pode ser outra pessoa.
        self.log["verificado_por"] = os.environ.get("USERNAME", "Desconhecido")
        self.log["data_fecho"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if qa is not None:
            self.log["qa_por_peca"] = qa
            # Agregado por critério (lido pelo export de auditoria): só "Sim" se
            # TODAS as peças cumprem esse critério.
            self.log["controlo_qualidade"] = {
                "inspecao_visual": all(r["inspecao_visual"] for r in qa.values()),
                "controlo_dimensional": all(r["controlo_dimensional"] for r in qa.values()),
                "conformidade": all(r["conformidade"] for r in qa.values()),
            } if qa else {}

        self.log["nc_codigo"] = nc_sel.split(" - ", 1)[0] if nc_sel and nc_sel != _SEM_NC else ""

        # Fecha o loop CAPA: ações corretivas aplicadas (para os códigos da
        # ordem e das peças) e notas livres sobre a correção.
        if ProducaoService.ncs_da_producao(self.log):
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
                campos_relevantes=["estado", "tempo_real", "quantidade_real", "nc_codigo", "acoes_aplicadas", "qa_por_peca"],
            )

        self.callback_salvar(self.log)
        self.destroy()
