import re
from datetime import datetime
from database.json_manager import JSONManager
from config.paths import ARQUIVO_PEDIDOS

class PedidoService:

    @staticmethod
    def formatar_codigo(id_pedido) -> str:
        """Código profissional para mostrar ao utilizador (ex: PED000007).
        O id interno (inteiro, usado em todas as ligações/joins) não muda."""
        try:
            return f"PED{int(id_pedido):06d}"
        except (TypeError, ValueError):
            return str(id_pedido)

    @staticmethod
    def extrair_id(codigo):
        """Inverso de formatar_codigo — aceita 'PED000007', '7' ou já um int."""
        if isinstance(codigo, int):
            return codigo
        digitos = re.sub(r"\D", "", str(codigo))
        return int(digitos) if digitos else None

    TECNOLOGIAS = ("FDM", "SLA", "SLS")

    @staticmethod
    def normalizar_data_entrega(data_str: str):
        """Aceita AAAA-MM-DD, DD/MM/AAAA ou DD-MM-AAAA e devolve AAAA-MM-DD,
        ou None se a data não for válida."""
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime((data_str or "").strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    @staticmethod
    def validar_dados_pedido(requerente: str, projeto: str, tecnologia: str,
                             data_entrega: str, pecas: list) -> list:
        """Valida os campos de um pedido antes de o criar/editar e devolve TODOS
        os erros encontrados (lista vazia = válido), para a UI os mostrar de uma
        vez em vez de um popup por campo.

        pecas: [{"pn": str, "material": str, "qtd": str}] tal como vêm da UI.
        Tecnologia e material são obrigatórios: um pedido sem tecnologia nunca
        aparece na seleção de Nova Produção (que filtra por tecnologia), e o
        material é o que permite agrupar pedidos numa mesma produção."""
        erros = []
        if not (requerente or "").strip():
            erros.append("Indique o requerente.")
        if not (projeto or "").strip():
            erros.append("Escolha o projeto.")
        if tecnologia not in PedidoService.TECNOLOGIAS:
            erros.append("Escolha a tecnologia (FDM, SLA ou SLS).")
        if not (data_entrega or "").strip():
            erros.append("Indique a data de entrega.")
        elif PedidoService.normalizar_data_entrega(data_entrega) is None:
            erros.append("Data de entrega inválida — use AAAA-MM-DD ou DD/MM/AAAA.")

        if not pecas:
            erros.append("O pedido deve conter pelo menos uma peça.")
        for i, peca in enumerate(pecas, start=1):
            pn = (peca.get("pn") or "").strip()
            nome = f"'{pn}'" if pn else f"da linha {i}"
            qtd = (peca.get("qtd") or "").strip()
            if not pn:
                erros.append(f"Peça da linha {i}: falta o Part Number.")
            if not (peca.get("material") or "").strip():
                erros.append(f"Peça {nome}: escolha o material.")
            if not qtd.isdigit() or int(qtd) <= 0:
                erros.append(f"Peça {nome}: a quantidade tem de ser um número inteiro maior que zero.")
        return erros

    ESTADOS_ABERTOS = ("Pendente", "Em Andamento")
    ESTADOS_FECHADOS = ("Concluído", "Entregue")

    @staticmethod
    def progresso(pedido: dict) -> tuple:
        """(unidades produzidas, unidades pedidas) somando todas as peças.
        `qtd_produzida` é atualizada ao fechar ordens (`registar_pecas_produzidas`)."""
        feitas = total = 0
        for peca in pedido.get("pecas", []):
            try:
                pedida = int(peca.get("qtd_solicitada", 0) or 0)
                produzida = int(peca.get("qtd_produzida", 0) or 0)
            except (TypeError, ValueError):
                continue
            total += pedida
            feitas += min(produzida, pedida)
        return feitas, total

    @staticmethod
    def estado_sugerido(pedido: dict) -> str:
        """Estado que o progresso das peças sugere: Concluído quando todas as
        peças estão produzidas, Em Andamento quando há algo feito ou ordens
        vinculadas. Nunca sugere recuar um pedido já Entregue."""
        estado = pedido.get("estado", "Pendente")
        if estado == "Entregue":
            return estado
        feitas, total = PedidoService.progresso(pedido)
        if total and feitas >= total:
            return "Concluído"
        if feitas or pedido.get("producoes_vinculadas"):
            return "Em Andamento"
        return estado

    @staticmethod
    def dias_ate_prazo(pedido: dict, hoje=None):
        """Dias até à data de entrega (negativo = atrasado), ou None sem data válida."""
        data = PedidoService.normalizar_data_entrega(pedido.get("data_entrega", ""))
        if not data:
            return None
        hoje = hoje or datetime.now().date()
        return (datetime.strptime(data, "%Y-%m-%d").date() - hoje).days

    @staticmethod
    def registar_pecas_produzidas(aprovadas) -> list:
        """Fecho do ciclo ordem → pedido. `aprovadas` é {chave: unidades aprovadas},
        com as chaves "id_pedido:pn:índice" do controlo de qualidade por peça:
        cada peça do pedido avança essas unidades (nunca além do pedido). Valores
        negativos descontam (correção de um fecho anterior), nunca abaixo de 0.

        Também aceita uma lista de chaves (ordens antigas, sem quantidades por
        peça): nesse caso a peça fica toda produzida.

        Devolve os pedidos alterados (já com `qtd_produzida` atualizada), para a
        UI propor o estado sugerido a cada um."""
        if isinstance(aprovadas, (list, tuple, set)):
            aprovadas = {chave: None for chave in aprovadas}
        por_pedido = {}
        for chave, qtd in aprovadas.items():
            partes = str(chave).split(":")
            if len(partes) < 3:
                continue
            try:
                pid, idx = int(partes[0]), int(partes[-1])
                qtd = None if qtd is None else int(qtd)
            except (TypeError, ValueError):
                continue
            if qtd == 0:
                continue
            atual = por_pedido.setdefault(pid, {})
            atual[idx] = None if (qtd is None or atual.get(idx, 0) is None) else atual.get(idx, 0) + qtd
        if not por_pedido:
            return []

        hoje = datetime.now().strftime("%Y-%m-%d")
        alterados = []

        def _transformar(pedidos):
            for p in pedidos:
                indices = por_pedido.get(p.get("id"))
                if not indices:
                    continue
                mudou = False
                for idx, peca in enumerate(p.get("pecas", [])):
                    if idx in indices:
                        try:
                            pedida = int(peca.get("qtd_solicitada", 0) or 0)
                            produzida = int(peca.get("qtd_produzida", 0) or 0)
                        except (TypeError, ValueError):
                            continue
                        nova = pedida if indices[idx] is None else max(0, min(pedida, produzida + indices[idx]))
                        if nova != produzida:
                            peca["qtd_produzida"] = nova
                            mudou = True
                if mudou:
                    p["data_atualizacao"] = hoje
                    alterados.append(dict(p))
            return pedidos

        JSONManager.atualizar(ARQUIVO_PEDIDOS, _transformar)
        return alterados

    @staticmethod
    def obter_todos():
        """Retorna todos os pedidos ordenados do mais recente para o mais antigo."""
        pedidos = JSONManager.carregar(ARQUIVO_PEDIDOS)
        pedidos.sort(key=lambda x: int(x.get("id", 0)), reverse=True)
        return pedidos

    @staticmethod
    def obter_por_id(id_pedido):
        """Devolve o pedido com o id indicado, ou None se não existir."""
        for p in PedidoService.obter_todos():
            if p.get("id") == id_pedido:
                return p
        return None

    @staticmethod
    def criar_pedido(requerente_email: str, nr_projeto: str, nome_projeto: str, tecnologia: str,
                      data_entrega: str, link_arquivos: str, observacoes: str, pecas: list):
        """Aplica a regra de negócio para gerar um novo ID e salvar o pedido."""
        hoje = datetime.now().strftime("%Y-%m-%d")
        novo_pedido = {}

        def _transformar(pedidos):
            novo_id = max([int(p.get("id", 0)) for p in pedidos]) + 1 if pedidos else 1
            novo_pedido.update({
                "id": novo_id,
                "requerente_email": requerente_email,
                "nr_projeto": nr_projeto,
                "nome_projeto": nome_projeto,
                "tecnologia": tecnologia,
                "observacoes": observacoes,
                "data_pedido": hoje,
                "data_entrega": data_entrega,
                "data_atualizacao": hoje,
                "link_arquivos": link_arquivos,
                "estado": "Pendente",
                "pecas": pecas,
                "producoes_vinculadas": []
            })
            pedidos.append(novo_pedido)
            return pedidos

        # Lê, calcula o novo ID e grava sob um único lock, para dois pedidos
        # criados ao mesmo tempo (rede partilhada) não colidirem no mesmo ID.
        JSONManager.atualizar(ARQUIVO_PEDIDOS, _transformar)
        return novo_pedido

    @staticmethod
    def atualizar_pedido(pedido_atualizado: dict):
        """Substitui o pedido com o mesmo id e renova a data de atualização."""
        pedido_atualizado["data_atualizacao"] = datetime.now().strftime("%Y-%m-%d")

        def _transformar(pedidos):
            for idx, p in enumerate(pedidos):
                if p.get("id") == pedido_atualizado.get("id"):
                    pedidos[idx] = pedido_atualizado
                    break
            return pedidos

        JSONManager.atualizar(ARQUIVO_PEDIDOS, _transformar)
        return pedido_atualizado

    @staticmethod
    def alterar_estado(id_pedido, novo_estado: str):
        """Atualiza só o estado do pedido, renovando a data de atualização —
        para não haver dois caminhos (edição completa vs. troca rápida de
        estado) com regras diferentes sobre quando essa data é tocada."""
        hoje = datetime.now().strftime("%Y-%m-%d")

        def _transformar(pedidos):
            for p in pedidos:
                if p.get("id") == id_pedido:
                    p["estado"] = novo_estado
                    p["data_atualizacao"] = hoje
                    break
            return pedidos

        JSONManager.atualizar(ARQUIVO_PEDIDOS, _transformar)

    @staticmethod
    def eliminar_pedido(id_pedido):
        """Soft delete: marca o pedido como inativo e cancelado, mantendo o
        registo na base de dados."""
        hoje = datetime.now().strftime("%Y-%m-%d")

        def _transformar(pedidos):
            for p in pedidos:
                if p.get("id") == id_pedido:
                    p["ativo"] = False
                    p["estado"] = "Cancelado"
                    p["data_atualizacao"] = hoje
                    break
            return pedidos

        JSONManager.atualizar(ARQUIVO_PEDIDOS, _transformar)


    @staticmethod
    def importar_de_email(texto: str, lista_projetos_fmt: list, lista_materiais_fmt: list) -> dict:
        """Extrai campos de um email estruturado e devolve um dicionário com os
        dados pré-preenchidos para a UI. Não guarda nada — apenas faz parsing.
        Retorna: {requerente, nr_projeto, nome_projeto, tecnologia, data_entrega,
                  link_arquivos, observacoes, pecas: [{pn, material, qtd}]}"""
        import re
        from datetime import datetime

        padrao = r"(?i)(TAREFA:|PROJETO:|RESPONSÁVEL:|REQUERENTE:|LINK FICHEIROS:|CRITÉRIOS DE ACEITAÇÃO:|PRAZO DE ENTREGA:|OBSERVAÇÕES:|LISTA DE PEÇAS:)"
        partes = re.split(padrao, texto)

        dados: dict = {}
        chave = None
        for p in partes:
            limpo = p.strip()
            if not limpo:
                continue
            if re.match(padrao, limpo):
                chave = limpo.upper().replace(":", "")
                dados[chave] = ""
            elif chave:
                dados[chave] += limpo + " "

        # ── Projeto ──────────────────────────────────────────────────────
        proj_extraido = dados.get("PROJETO", "").strip()
        link = dados.get("LINK FICHEIROS", "").strip()
        nr_proj = nome_proj = ""
        for p_fmt in lista_projetos_fmt:
            if p_fmt == "Sem projetos registados":
                continue
            if proj_extraido and proj_extraido.lower() in p_fmt.lower():
                partes_p = p_fmt.split(" - ", 1)
                nr_proj, nome_proj = partes_p[0], (partes_p[1] if len(partes_p) > 1 else "")
                break
        if not nr_proj and link:
            for p_fmt in lista_projetos_fmt:
                if p_fmt == "Sem projetos registados":
                    continue
                nome_p = p_fmt.split(" - ")[-1]
                palavras = [w.lower() for w in nome_p.split() if len(w) > 3]
                if any(w in link.lower() for w in palavras):
                    partes_p = p_fmt.split(" - ", 1)
                    nr_proj, nome_proj = partes_p[0], (partes_p[1] if len(partes_p) > 1 else "")
                    break

        # ── Data de entrega ───────────────────────────────────────────────
        prazo_raw = dados.get("PRAZO DE ENTREGA", "").strip()
        data_entrega = ""
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                data_entrega = datetime.strptime(prazo_raw, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
        if not data_entrega:
            data_entrega = prazo_raw  # guarda o raw para a UI mostrar erro

        # ── Tecnologia + observações ──────────────────────────────────────
        obs_raw = dados.get("OBSERVAÇÕES", "").strip()
        crit    = dados.get("CRITÉRIOS DE ACEITAÇÃO", "").strip()

        obs_upper = obs_raw.upper()
        tecnologia = ("SLS" if "SLS" in obs_upper else
                      "SLA" if "SLA" in obs_upper else "FDM")

        partes_obs = [p.strip() for p in obs_raw.replace("\n", ";").split(";") if p.strip()]
        material_inferido = ""
        obs_restantes = []
        for p in partes_obs:
            p_lower = p.lower()
            if p_lower.startswith("tecnologia"):
                continue
            elif p_lower.startswith("material") and ":" in p:
                material_inferido = p.split(":", 1)[1].strip()
            else:
                obs_restantes.append(p)

        obs_final = ""
        if crit:
            obs_final += f"Critérios de Aceitação: {crit}\n"
        if obs_restantes:
            obs_final += "; ".join(obs_restantes)

        # ── Lista de peças ────────────────────────────────────────────────
        pn_inferido = link.replace("/", "\\").split("\\")[-1] if link else ""
        texto_pecas = dados.get("LISTA DE PEÇAS", "").strip()
        pecas: list[dict] = []

        def _match_material(nome: str) -> str:
            for m_fmt in lista_materiais_fmt:
                if nome.lower() in m_fmt.lower():
                    return m_fmt
            return nome

        if texto_pecas:
            segs = [s.strip() for s in texto_pecas.split(";") if s.strip()]
            pn_atual = segs[0] if segs else "S/N"
            idx = 1
            while idx < len(segs):
                mat_atual = segs[idx]
                qtd_raw = segs[idx + 1] if (idx + 1) < len(segs) else "1"
                m = re.match(r"^(\d+)\s*(.*)$", qtd_raw)
                qtd_atual  = m.group(1) if m else "1"
                pn_proximo = m.group(2).strip() if m else qtd_raw.strip()
                pecas.append({"pn": pn_atual, "material": _match_material(mat_atual),
                              "qtd": qtd_atual})
                pn_atual = pn_proximo
                idx += 2
                if not pn_atual and idx < len(segs):
                    pn_atual = segs[idx]
                    idx += 1
        elif material_inferido or pn_inferido:
            pecas.append({"pn": pn_inferido, "material": _match_material(material_inferido),
                          "qtd": "1"})

        return {
            "nr_projeto":   nr_proj,
            "nome_projeto": nome_proj,
            "tecnologia":   tecnologia,
            "data_entrega": data_entrega,
            "link_arquivos": link,
            "observacoes":  obs_final.strip(),
            "pecas":        pecas,
        }

    @staticmethod
    def vincular_producao(ids_pedidos: list, id_producao):
        """Liga uma produção aos pedidos que ela cobre: regista o id da
        produção em 'producoes_vinculadas' (link inverso, hoje nunca escrito)
        e marca os pedidos como Em Andamento."""
        hoje = datetime.now().strftime("%Y-%m-%d")

        ESTADOS_FINAIS = {"Entregue", "Concluído"}

        def _transformar(pedidos):
            for p in pedidos:
                if p.get("id") in ids_pedidos:
                    vinculadas = p.setdefault("producoes_vinculadas", [])
                    if id_producao not in vinculadas:
                        vinculadas.append(id_producao)
                    # Não reverte um pedido já entregue/concluído para "Em Andamento"
                    if p.get("estado") not in ESTADOS_FINAIS:
                        p["estado"] = "Em Andamento"
                    p["data_atualizacao"] = hoje
            return pedidos

        JSONManager.atualizar(ARQUIVO_PEDIDOS, _transformar)