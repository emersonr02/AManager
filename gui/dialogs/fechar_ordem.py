import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import os
from datetime import datetime
from services.producao_service import ProducaoService
from services.pedido_service import PedidoService
from services.nc_service import NCService
from services.audit_service import AuditService
from gui import theme

class JanelaFecharOrdem(ctk.CTkToplevel):
    def __init__(self, parent, log_data, callback_salvar):
        super().__init__(parent)
        self.log = log_data
        # Cópia do estado original — usada no fecho para saber o que mudou
        # e alimentar a trilha de auditoria (só relevante quando a ordem
        # já tinha sido fechada antes e está a ser reaberta/corrigida).
        self._dados_antes_da_edicao = dict(log_data)
        self.callback_salvar = callback_salvar

        codigo_ordem = ProducaoService.formatar_codigo(self.log.get('id', ''))
        self.title(f"Tratamento e Fecho - Ordem #{codigo_ordem}")

        # Janela larga, com o corpo do formulário dentro de uma área
        # scrollável. O nº de checkboxes de ações corretivas varia consoante
        # o código NC escolhido — em vez de a janela crescer (empurrando o
        # botão de gravar para fora), o cabeçalho e o rodapé (botão +
        # assinatura) ficam sempre fixos; só o meio faz scroll.
        #
        # A ALTURA é calculada a partir do ecrã do utilizador, nunca fixa
        # em pixels absolutos: um valor fixo (ex: 760px) pode ultrapassar a
        # altura de ecrãs mais pequenos ou com escala de Windows >100%,
        # fazendo o rodapé (e o botão de gravar) ficar fisicamente fora da
        # área visível — mesmo que o *design* interno esteja correto.
        largura = 640
        self.update_idletasks()
        altura_ecra = self.winfo_screenheight()
        largura_ecra = self.winfo_screenwidth()
        altura = min(760, int(altura_ecra * 0.85))
        pos_x = max(0, (largura_ecra - largura) // 2)
        pos_y = max(0, (altura_ecra - altura) // 3)
        self.geometry(f"{largura}x{altura}+{pos_x}+{pos_y}")
        self.minsize(600, min(480, altura))
        self.configure(fg_color=theme.BG)
        self.resizable(False, True)  # permite esticar mais em ecrãs grandes, nunca encolher demasiado

        self.transient(parent)
        self.grab_set()

        self.extrair_dados_dinamicos()
        self.construir_layout()

    def extrair_dados_dinamicos(self):
        pedidos_db = PedidoService.obter_todos()
        vinculos = self.log.get("pedidos_vinculados", [])
        
        materiais_set = set()
        qa_gravado = self.log.get("qa_por_peca", {})
        self.linhas_qa_dados = []

        # 1. Formatar os IDs dos pedidos (Substituindo o Projeto)
        if vinculos:
            self.pedidos_fmt = ", ".join(PedidoService.formatar_codigo(v) for v in vinculos)

            # Aproveitar para extrair materiais e a lista de peças (QA por peça)
            # diretamente dos pedidos vinculados.
            for p in pedidos_db:
                if p.get("id") in vinculos:
                    for idx, peca in enumerate(p.get("pecas", [])):
                        if peca.get("material"): materiais_set.add(peca["material"])
                        # O índice entra na chave porque novo_pedido.py não impede PNs
                        # repetidos dentro do mesmo pedido — sem ele, duas linhas com o
                        # mesmo PN colidiriam na mesma entrada de QA.
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
        # nunca é empurrado para fora da janela, independentemente de
        # quantos checkboxes de ações corretivas aparecerem no meio.
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

        # --- CRITÉRIOS DE ACEITAÇÃO (POR PEÇA) ---
        frm_cq = ctk.CTkFrame(corpo, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        frm_cq.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(frm_cq, text="CRITÉRIOS DE ACEITAÇÃO (CONTROLO DE QUALIDADE POR PEÇA)", font=theme.font_eyebrow(9), text_color=theme.TEXT_MUTED).pack(anchor="w", padx=15, pady=(10, 5))

        checkbox_kwargs = dict(fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, checkmark_color=theme.WHITE, border_color=theme.TEXT_MUTED, text_color=theme.TEXT)
        self.linhas_qa = []

        if not self.linhas_qa_dados:
            ctk.CTkLabel(frm_cq, text="Sem peças associadas a esta ordem.", font=theme.font_body(11), text_color=theme.TEXT_MUTED).pack(anchor="w", padx=15, pady=(0, 10))
        else:
            frm_scroll_qa = ctk.CTkScrollableFrame(frm_cq, fg_color=theme.SURFACE_ALT, height=180, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_S)
            frm_scroll_qa.pack(fill="x", padx=15, pady=(0, 10))

            for peca in self.linhas_qa_dados:
                linha_frm = ctk.CTkFrame(frm_scroll_qa, fg_color="transparent")
                linha_frm.pack(fill="x", pady=4)

                rotulo = f"{PedidoService.formatar_codigo(peca['pedido_id'])} · {peca['pn']} ({peca['material']}, qtd {peca['qtd']})"
                ctk.CTkLabel(linha_frm, text=rotulo, font=theme.font_body(11), text_color=theme.TEXT, anchor="w", width=220, wraplength=210, justify="left").pack(side="left", padx=(5, 10))

                gravado = peca["gravado"]
                v_visual = tk.BooleanVar(value=bool(gravado.get("inspecao_visual")))
                v_dimens = tk.BooleanVar(value=bool(gravado.get("controlo_dimensional")))
                v_conform = tk.BooleanVar(value=bool(gravado.get("conformidade")))

                ctk.CTkCheckBox(linha_frm, text="Visual", font=theme.font_body(10), variable=v_visual, width=1, **checkbox_kwargs).pack(side="left", expand=True)
                ctk.CTkCheckBox(linha_frm, text="Dimensional", font=theme.font_body(10), variable=v_dimens, width=1, **checkbox_kwargs).pack(side="left", expand=True)
                ctk.CTkCheckBox(linha_frm, text="Conformidade", font=theme.font_body(10), variable=v_conform, width=1, **checkbox_kwargs).pack(side="left", expand=True)

                self.linhas_qa.append({
                    "chave": peca["chave"],
                    "visual": v_visual, "dimensional": v_dimens, "conformidade": v_conform,
                })

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

        # Impede fechar a ordem se alguma peça não tiver a qualidade toda aprovada
        # (Opcional: podes remover este bloco se for permitido fechar sem os 3 checks).
        # Nota: all([]) é True — uma ordem sem peças vinculadas não bloqueia.
        todas_completas = all(
            v["visual"].get() and v["dimensional"].get() and v["conformidade"].get()
            for v in self.linhas_qa
        )
        if est_final == "Concluída" and not todas_completas:
            if not messagebox.askyesno("Aviso de Qualidade", "Atenção: Nem todas as peças têm os critérios de aceitação validados.\nDesejas concluir a ordem mesmo assim?"):
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
        # Agregado derivado do detalhe por peça — cada critério só é "Sim"
        # se TODAS as peças passaram nesse critério especificamente (ex: se
        # uma peça falhou só o dimensional, isso não deve apagar que todas
        # passaram no visual). Mantém o export de auditoria (que lê
        # "controlo_qualidade") coerente com o novo detalhe por peça, sem
        # precisar de reescrever export_service.py.
        self.log["controlo_qualidade"] = {
            "inspecao_visual": all(v["visual"].get() for v in self.linhas_qa),
            "controlo_dimensional": all(v["dimensional"].get() for v in self.linhas_qa),
            "conformidade": all(v["conformidade"].get() for v in self.linhas_qa),
        } if self.linhas_qa else {}

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

        # Trilha de auditoria: se esta ordem já tinha sido fechada antes
        # (reabertura para correção), regista o que mudou desde o último
        # fecho. Sem isto, uma correção posterior não deixava rasto de
        # quem alterou o quê e para que valor.
        if self._dados_antes_da_edicao.get("verificado_por"):
            AuditService.registrar_diferencas(
                entidade="producao",
                id_entidade=self.log.get("id"),
                dados_antigos=self._dados_antes_da_edicao,
                dados_novos=self.log,
                campos_relevantes=[
                    "estado", "tempo_real", "quantidade_real",
                    "nc_codigo", "acoes_aplicadas",
                ],
            )

        self.callback_salvar(self.log)
        self.destroy()
