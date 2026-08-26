"""
PedidoService — sobre SQLite.

Mudança importante face à versão JSON: 'producoes_vinculadas' deixa de ser
um campo guardado (que era preciso manter manualmente em sincronia) e passa
a ser DERIVADO da tabela producao_pedidos — a mesma que ProducaoService já
usa para o sentido oposto. Deixa de haver duas fontes de verdade para a
mesma relação, eliminando a possibilidade de divergirem entre si.
"""
import re
from datetime import datetime

from database.sqlite_manager import SQLiteManager


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

    # ── Acesso a dados ──────────────────────────────────────────────────────

    @staticmethod
    def _montar_dict(con, row) -> dict:
        """Reconstrói o dict do pedido no mesmo formato que a UI já espera:
        com a lista de peças embutida e o link inverso para as produções."""
        d = dict(row)
        pid = d["id"]

        pecas = con.execute(
            "SELECT pn, material, qtd_solicitada, qtd_produzida FROM pedido_pecas "
            "WHERE pedido_id = ? ORDER BY ordem",
            (pid,),
        ).fetchall()
        d["pecas"] = [dict(p) for p in pecas]

        # Derivado da tabela N:N, em vez de guardado num campo próprio
        vinculadas = con.execute(
            "SELECT producao_id FROM producao_pedidos WHERE pedido_id = ? ORDER BY producao_id",
            (pid,),
        ).fetchall()
        d["producoes_vinculadas"] = [v["producao_id"] for v in vinculadas]

        d["ativo"] = bool(d.get("ativo", 1))
        return d

    @staticmethod
    def obter_todos():
        """Retorna todos os pedidos ordenados do mais recente para o mais antigo."""
        with SQLiteManager.conectar() as con:
            rows = con.execute("SELECT * FROM pedidos ORDER BY id DESC").fetchall()
            return [PedidoService._montar_dict(con, r) for r in rows]

    @staticmethod
    def obter_por_id(id_pedido):
        """Devolve o pedido com o id indicado, ou None se não existir."""
        with SQLiteManager.conectar() as con:
            row = con.execute("SELECT * FROM pedidos WHERE id = ?", (id_pedido,)).fetchone()
            if row is None:
                return None
            return PedidoService._montar_dict(con, row)

    @staticmethod
    def criar_pedido(requerente_email: str, nr_projeto: str, nome_projeto: str, tecnologia: str,
                      data_entrega: str, link_arquivos: str, observacoes: str, pecas: list):
        """Cria um pedido novo. O ID é atribuído pelo SQLite (AUTOINCREMENT),
        que garante unicidade mesmo com vários utilizadores em simultâneo —
        deixa de ser preciso calcular max(id)+1 à mão sob lock de ficheiro."""
        hoje = datetime.now().strftime("%Y-%m-%d")

        with SQLiteManager.conectar() as con:
            cur = con.execute(
                """INSERT INTO pedidos (requerente_email, nr_projeto, nome_projeto, tecnologia,
                    data_pedido, data_entrega, link_arquivos, observacoes, estado, ativo, data_atualizacao)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pendente', 1, ?)""",
                (requerente_email, nr_projeto, nome_projeto, tecnologia,
                 hoje, data_entrega, link_arquivos, observacoes, hoje),
            )
            novo_id = cur.lastrowid

            for ordem, peca in enumerate(pecas or []):
                con.execute(
                    "INSERT INTO pedido_pecas (pedido_id, pn, material, qtd_solicitada, qtd_produzida, ordem) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (novo_id, peca.get("pn", ""), peca.get("material", ""),
                     peca.get("qtd_solicitada", 0), peca.get("qtd_produzida", 0), ordem),
                )

            row = con.execute("SELECT * FROM pedidos WHERE id = ?", (novo_id,)).fetchone()
            return PedidoService._montar_dict(con, row)

    @staticmethod
    def atualizar_pedido(pedido_atualizado: dict):
        """Substitui o pedido com o mesmo id e renova a data de atualização.
        As peças são recriadas de raiz a partir da lista recebida."""
        hoje = datetime.now().strftime("%Y-%m-%d")
        pid = pedido_atualizado.get("id")

        with SQLiteManager.conectar() as con:
            con.execute(
                """UPDATE pedidos SET
                    requerente_email=?, nr_projeto=?, nome_projeto=?, tecnologia=?,
                    data_entrega=?, link_arquivos=?, observacoes=?, estado=?,
                    ativo=?, data_atualizacao=?
                   WHERE id=?""",
                (
                    pedido_atualizado.get("requerente_email", ""),
                    pedido_atualizado.get("nr_projeto", ""),
                    pedido_atualizado.get("nome_projeto", ""),
                    pedido_atualizado.get("tecnologia", ""),
                    pedido_atualizado.get("data_entrega", ""),
                    pedido_atualizado.get("link_arquivos", ""),
                    pedido_atualizado.get("observacoes", ""),
                    pedido_atualizado.get("estado", "Em Andamento"),
                    1 if pedido_atualizado.get("ativo", True) else 0,
                    hoje, pid,
                ),
            )

            con.execute("DELETE FROM pedido_pecas WHERE pedido_id = ?", (pid,))
            for ordem, peca in enumerate(pedido_atualizado.get("pecas", []) or []):
                con.execute(
                    "INSERT INTO pedido_pecas (pedido_id, pn, material, qtd_solicitada, qtd_produzida, ordem) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (pid, peca.get("pn", ""), peca.get("material", ""),
                     peca.get("qtd_solicitada", 0), peca.get("qtd_produzida", 0), ordem),
                )

            row = con.execute("SELECT * FROM pedidos WHERE id = ?", (pid,)).fetchone()
            return PedidoService._montar_dict(con, row)

    @staticmethod
    def alterar_estado(id_pedido, novo_estado: str):
        """Atualiza só o estado do pedido, renovando a data de atualização —
        para não haver dois caminhos (edição completa vs. troca rápida de
        estado) com regras diferentes sobre quando essa data é tocada."""
        hoje = datetime.now().strftime("%Y-%m-%d")
        with SQLiteManager.conectar() as con:
            con.execute(
                "UPDATE pedidos SET estado = ?, data_atualizacao = ? WHERE id = ?",
                (novo_estado, hoje, id_pedido),
            )

    @staticmethod
    def eliminar_pedido(id_pedido):
        """Soft delete: marca o pedido como inativo e cancelado, mantendo o
        registo na base de dados."""
        hoje = datetime.now().strftime("%Y-%m-%d")
        with SQLiteManager.conectar() as con:
            con.execute(
                "UPDATE pedidos SET ativo = 0, estado = 'Cancelado', data_atualizacao = ? WHERE id = ?",
                (hoje, id_pedido),
            )

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
        """Liga uma produção aos pedidos que ela cobre e marca-os como
        Em Andamento. A ligação em si vive na tabela producao_pedidos —
        a mesma que ProducaoService usa —, por isso este método garante
        que ela existe e trata apenas da transição de estado do pedido."""
        hoje = datetime.now().strftime("%Y-%m-%d")
        ESTADOS_FINAIS = {"Entregue", "Concluído"}

        with SQLiteManager.conectar() as con:
            for pid in ids_pedidos or []:
                con.execute(
                    "INSERT OR IGNORE INTO producao_pedidos (producao_id, pedido_id) VALUES (?, ?)",
                    (id_producao, pid),
                )
                row = con.execute("SELECT estado FROM pedidos WHERE id = ?", (pid,)).fetchone()
                if row is None:
                    continue
                # Não reverte um pedido já entregue/concluído para "Em Andamento"
                if row["estado"] not in ESTADOS_FINAIS:
                    con.execute(
                        "UPDATE pedidos SET estado = 'Em Andamento', data_atualizacao = ? WHERE id = ?",
                        (hoje, pid),
                    )
                else:
                    con.execute(
                        "UPDATE pedidos SET data_atualizacao = ? WHERE id = ?", (hoje, pid),
                    )
