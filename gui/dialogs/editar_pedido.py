from services.pedido_service import PedidoService
from services.audit_service import AuditService
from gui import theme
from gui.dialogs.novo_pedido import FormularioPedido, mensagem_erros_pedido  # noqa: F401 (reexportado)


class JanelaEditarPedido(FormularioPedido):
    def __init__(self, parent, pedido, callback_atualizar):
        self.pedido = pedido
        # Cópia do estado original para alimentar a trilha de auditoria
        self._dados_antes_da_edicao = dict(pedido)
        codigo = PedidoService.formatar_codigo(pedido.get("id"))
        super().__init__(parent, f"Editar pedido {codigo}", "Guardar alterações", callback_atualizar)

    def _criar_campo_requerente(self, parent):
        self.ent_req = theme.entry(parent)
        return self.ent_req

    def preencher(self):
        """Preenche o formulário com os dados do pedido."""
        self.ent_req.insert(0, self.pedido.get("requerente_email", self.pedido.get("requerente", "")))
        self.ent_data.insert(0, self.pedido.get("data_entrega", ""))
        self.ent_link.insert(0, self.pedido.get("link_arquivos", ""))
        if self.pedido.get("observacoes"):
            self.txt_obs.insert("1.0", self.pedido.get("observacoes"))
        if self.pedido.get("tecnologia") in PedidoService.TECNOLOGIAS:
            self.cmb_tech.set(self.pedido["tecnologia"])

        nr_p = self.pedido.get("nr_projeto", self.pedido.get("projeto", ""))
        nome_p = self.pedido.get("nome_projeto", "")
        fmt = f"{nr_p} - {nome_p}" if nome_p else str(nr_p)
        if fmt in self.lista_projetos_fmt:
            self.cmb_proj.set(fmt)
        elif fmt:
            # Projeto entretanto desativado/renomeado: mantém o valor atual em vez
            # de trocar em silêncio para o primeiro projeto da lista (que alterava
            # o pedido sem o utilizador dar por isso ao gravar).
            self.cmb_proj.configure(values=[fmt] + [p for p in self.lista_projetos_fmt if p != "Sem projetos registados"])
            self.cmb_proj.set(fmt)

        pecas = self.pedido.get("pecas", [])
        for p in pecas:
            self.adicionar_linha_peca(pn=p.get("pn", ""), mat=p.get("material", ""),
                                      qtd=p.get("qtd_solicitada", 1), qtd_produzida=p.get("qtd_produzida", 0))
        if not pecas:
            self.adicionar_linha_peca()

    # Compatibilidade com o nome antigo
    def preencher_dados_existentes(self):
        self.preencher()

    def confirmar(self):
        self.salvar_alteracoes()

    def salvar_alteracoes(self):
        dados = self._ler_e_validar(self.ent_req.get().strip())
        if dados is None:
            return

        pedido_atualizado = dict(self.pedido)
        pedido_atualizado.update(dados)
        PedidoService.atualizar_pedido(pedido_atualizado)

        # Trilha de auditoria: regista o que mudou nesta edição.
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

        theme.toast(self, f"Pedido {PedidoService.formatar_codigo(self.pedido.get('id'))} atualizado.")
        self.callback_atualizar()
        self.destroy()
