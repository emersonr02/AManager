import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import os
from database.json_manager import JSONManager
from config.paths import ARQUIVO_PEDIDOS
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
        # Aumentada a altura da janela para garantir que o botão aparece perfeitamente
        self.geometry("520x800")
        self.configure(fg_color=theme.BG)
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()

        self.extrair_dados_dinamicos()
        self.construir_layout()

    def extrair_dados_dinamicos(self):
        pedidos_db = JSONManager.carregar(ARQUIVO_PEDIDOS) if os.path.exists(ARQUIVO_PEDIDOS) else []
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
        self.maquina = self.log.get("maquina", "N/A")
        self.tecnologia = self.log.get("tecnologia", "FDM")
        self.tempo_est = self.log.get("tempo_estimado", self.log.get("tempo", "00:00"))
        self.responsavel = self.log.get("operador", "N/A")
        
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
            self.qtd_raw = self.log.get("quantidade_consumida", 0.0)
            self.qtd_est = str(self.qtd_raw)

    def construir_layout(self):
        codigo_ordem = ProducaoService.formatar_codigo(self.log.get('id', ''))
        ctk.CTkLabel(self, text=f"Tratamento e Fecho - Ordem #{codigo_ordem}", font=theme.font_display(16), text_color=theme.ACCENT).pack(pady=(20, 10))

        # --- RESUMO DO PLANEAMENTO ---
        frm_resumo = ctk.CTkFrame(self, fg_color=theme.SURFACE_ALT, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        frm_resumo.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(frm_resumo, text="RESUMO DO PLANEAMENTO", font=theme.font_eyebrow(10), text_color=theme.TEAL).pack(anchor="w", padx=15, pady=(10, 5))

        # Agora apresenta os Pedidos em vez do Projeto
        info_texto = f"Máquina: {self.maquina} | Pedidos: {self.pedidos_fmt}\nMaterial: {self.material_fmt} | Tecnologia: {self.tecnologia}\nTempo Est.: {self.tempo_est} | Qtd Est.: {self.qtd_est} g/ml\nResponsável: {self.responsavel}"
        ctk.CTkLabel(frm_resumo, text=info_texto, font=theme.font_mono(11), text_color=theme.TEXT, justify="left").pack(anchor="w", padx=15, pady=(0, 10))

        # --- APONTAMENTO REAL ---
        frm_real = ctk.CTkFrame(self, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        frm_real.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(frm_real, text="Apontamento Real de Produção", font=theme.font_body(12, "bold"), text_color=theme.ACCENT).pack(anchor="w", padx=15, pady=(10, 10))

        # Tempo Real
        frm_tr = ctk.CTkFrame(frm_real, fg_color="transparent")
        frm_tr.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(frm_tr, text="Tempo Real (HH:MM):", font=theme.font_body(11), text_color=theme.TEXT_MUTED, width=120, anchor="e").pack(side="left", padx=(0, 10))
        self.ent_tempo_real = theme.entry(frm_tr, width=150, font=theme.font_mono(12))

        t_real_gravado = self.log.get("tempo_real", "")
        self.ent_tempo_real.insert(0, t_real_gravado if t_real_gravado else str(self.tempo_est))
        self.ent_tempo_real.pack(side="left")

        # Quantidade Real
        frm_qr = ctk.CTkFrame(frm_real, fg_color="transparent")
        frm_qr.pack(fill="x", padx=15, pady=(5, 15))
        ctk.CTkLabel(frm_qr, text="Quantidade Real (g/ml):", font=theme.font_body(11), text_color=theme.TEXT_MUTED, width=120, anchor="e").pack(side="left", padx=(0, 10))
        self.ent_qtd_real = theme.entry(frm_qr, width=150, font=theme.font_mono(12))

        q_real_gravado = self.log.get("quantidade_real", "")
        try:
            val_inserir = str(round(float(q_real_gravado), 2)) if q_real_gravado else str(round(float(self.qtd_raw), 2))
            self.ent_qtd_real.insert(0, val_inserir)
        except (ValueError, TypeError):
            self.ent_qtd_real.insert(0, str(q_real_gravado if q_real_gravado else self.qtd_raw))

        self.ent_qtd_real.pack(side="left")

        # --- ESTADO FINAL ---
        ctk.CTkLabel(self, text="ESTADO FINAL DA ORDEM", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).pack(anchor="w", padx=20, pady=(15, 5))
        self.cmb_estado = theme.combobox(self, values=["Concluída", "Cancelada", "Em Andamento"], width=460, state="readonly")

        # Agora reflete o estado real da ordem (não assume mais que está concluída)
        estado_atual = self.log.get("estado", "Em Andamento")
        if estado_atual == "A Imprimir": estado_atual = "Em Andamento"
        self.cmb_estado.set(estado_atual)
        self.cmb_estado.pack(padx=20, pady=5)

        # --- CRITÉRIOS DE ACEITAÇÃO (POR PEÇA) ---
        frm_cq = ctk.CTkFrame(self, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
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
        frm_nc = ctk.CTkFrame(self, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        frm_nc.pack(fill="x", padx=20, pady=(0, 15))
        ctk.CTkLabel(frm_nc, text="NÃO-CONFORMIDADE (SE APLICÁVEL)", font=theme.font_eyebrow(9), text_color=theme.TEXT_MUTED).pack(anchor="w", padx=15, pady=(10, 5))

        valores_nc = ["Nenhuma"] + NCService.obter_nc_por_tecnologia(self.tecnologia)
        self.cmb_nc = theme.combobox(frm_nc, values=valores_nc, width=460, state="readonly", command=self.on_nc_selecionada)
        self.cmb_nc.pack(padx=15, pady=(0, 5), anchor="w")

        self.lbl_acoes_nc = ctk.CTkLabel(frm_nc, text="", font=theme.font_body(10), text_color=theme.TEXT_MUTED, justify="left", wraplength=440)
        self.lbl_acoes_nc.pack(anchor="w", padx=15, pady=(0, 10))

        nc_gravado = self.log.get("nc_codigo", "")
        valor_inicial = next((v for v in valores_nc if v.startswith(f"{nc_gravado} -")), "Nenhuma") if nc_gravado else "Nenhuma"
        self.cmb_nc.set(valor_inicial)
        self.on_nc_selecionada(valor_inicial)

        # Botão com margem extra em baixo (pady)
        self.btn_salvar = theme.button_primary(self, text="SALVAR APONTAMENTO E FECHAR", font=theme.font_body(12, "bold"), height=45, command=self.salvar)
        self.btn_salvar.pack(fill="x", padx=20, pady=(10, 20))

    def on_nc_selecionada(self, valor):
        """Mostra as ações corretivas sugeridas para o código NC escolhido."""
        if not valor or valor == "Nenhuma":
            self.lbl_acoes_nc.configure(text="")
            return

        cod = valor.split(" - ", 1)[0]
        acoes = NCService.obter_acoes_por_cod(cod)
        if not acoes:
            self.lbl_acoes_nc.configure(text="Sem ações corretivas associadas a este código.")
            return

        linhas = "\n".join(f"• {a.get('acao')}" for a in acoes)
        self.lbl_acoes_nc.configure(text=f"Ações corretivas sugeridas:\n{linhas}")

    def salvar(self):
        t_real = self.ent_tempo_real.get().strip()
        q_real = self.ent_qtd_real.get().strip()
        est_final = self.cmb_estado.get()

        if not t_real or not q_real:
            messagebox.showerror("Erro", "Preencha o Tempo Real e a Quantidade Real antes de fechar a ordem.")
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

        self.log["qa_por_peca"] = {
            v["chave"]: {
                "inspecao_visual": v["visual"].get(),
                "controlo_dimensional": v["dimensional"].get(),
                "conformidade": v["conformidade"].get(),
            }
            for v in self.linhas_qa
        }

        nc_sel = self.cmb_nc.get()
        self.log["nc_codigo"] = nc_sel.split(" - ", 1)[0] if nc_sel and nc_sel != "Nenhuma" else ""

        self.callback_salvar(self.log)
        self.destroy()