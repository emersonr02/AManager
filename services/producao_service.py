"""
ProducaoService — sobre SQLite. Este é o service mais complexo da
aplicação: junta duas tabelas N:N (pedidos vinculados, ações corretivas
aplicadas) e duas colunas JSON (checklist_seguranca, controlo_qualidade)
para reconstruir o mesmo formato de dict que o resto do código (gui/,
export_service, pdf_service) já espera.

Toda a lógica pura (formatar_codigo, converter_para_horas, normalizar_*,
etc.) manteve-se exatamente igual — não faz I/O, não precisava de mudar.
"""
import json
import re
from datetime import datetime

from database.sqlite_manager import SQLiteManager


class ProducaoService:

    # ── Utilitários puros — idênticos à versão JSON, sem alterações ────────

    @staticmethod
    def formatar_codigo(id_producao) -> str:
        """Código profissional para mostrar ao utilizador (ex: PRD000012).
        O id interno (inteiro, usado em todas as ligações/joins) não muda."""
        try:
            return f"PRD{int(id_producao):06d}"
        except (TypeError, ValueError):
            return str(id_producao)

    @staticmethod
    def extrair_id(codigo):
        """Inverso de formatar_codigo — aceita 'PRD000012', '12' ou já um int."""
        if isinstance(codigo, int):
            return codigo
        digitos = re.sub(r"\D", "", str(codigo))
        return int(digitos) if digitos else None

    @staticmethod
    def validar_formato_tempo(tempo_str: str) -> bool:
        """Valida se a string está no formato exato HH:MM"""
        return bool(re.match(r"^\d{2}:\d{2}$", tempo_str.strip()))

    @staticmethod
    def validar_numero_positivo(valor_str: str) -> bool:
        """Valida se a string representa um número > 0 (aceita vírgula ou ponto decimal)."""
        try:
            return float(valor_str.strip().replace(',', '.')) > 0
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def converter_para_horas(hhmm: str) -> float:
        """Converte tempo para float de horas.
        Suporta todos os formatos legacy:
          - 'HH:MM'             → formato padrão atual
          - 'H:MM:SS'           → formato antigo com segundos
          - 'N days, H:MM:SS'  → timedelta do Python (jobs > 24h)
        """
        try:
            s = str(hhmm).strip()
            dias = 0
            if 'day' in s:
                partes_dia = s.split(', ', 1)
                dias = int(partes_dia[0].split()[0])
                s = partes_dia[1] if len(partes_dia) > 1 else "0:00"
            partes = s.split(':')
            h = int(partes[0])
            m = int(partes[1]) if len(partes) > 1 else 0
            return dias * 24 + h + m / 60
        except (ValueError, TypeError, IndexError):
            return 0.0

    @staticmethod
    def converter_para_string(horas_float: float) -> str:
        """Converte float para string 'HH:MM' (ex: 1.5 -> '01:30')"""
        h = int(horas_float)
        m = int(round((horas_float - h) * 60))
        if m == 60:
            h += 1
            m = 0
        return f"{h:02d}:{m:02d}"

    @staticmethod
    def calcular_consumo_sls(altura_mm: float, perc_po_novo: float,
                             largura_cuba: float = 381.0,
                             profundidade_cuba: float = 330.0,
                             densidade_po: float = 0.45) -> float:
        """Calcula o consumo de pó em kg."""
        volume_mm3 = largura_cuba * profundidade_cuba * altura_mm
        peso_total_kg = (volume_mm3 / 1_000_000) * densidade_po
        consumo_real_kg = peso_total_kg * perc_po_novo
        return round(consumo_real_kg, 4)

    @staticmethod
    def estimar_quantidade(producao: dict) -> str:
        """Quantidade estimada de uma produção, num formato pronto a mostrar."""
        if producao.get("tecnologia") == "SLS":
            try:
                altura = float(str(producao.get("altura_cuba", 0)).replace(",", "."))
                perc = float(str(producao.get("percentagem_po_novo", 0)).replace(",", "."))
                if perc > 1:
                    perc = perc / 100
                return f"{ProducaoService.calcular_consumo_sls(altura, perc):.2f}"
            except ValueError:
                return ""
        return str(producao.get("quantidade_consumida", ""))

    # Mapeamento de IDs legacy para nomes completos de máquinas — usado só
    # como último recurso; dados migrados já vêm com o nome resolvido.
    _LEGACY_MAQUINAS = {
        "X1-1": "Bambu Lab X1C #1", "X1-2": "Bambu Lab X1C #2", "X1-3": "Bambu Lab X1C #3",
        "P1-1": "Bambu Lab P1S #1", "P1-2": "Bambu Lab P1S #2",
        "Form3L": "Formlabs Form 3L", "SLS-380": "3D Systems SLS 380",
    }

    @staticmethod
    def normalizar_maquina(producao: dict, id_para_nome: dict = None) -> str:
        """Resolve o nome completo da máquina de uma produção. Com dados já
        migrados para SQLite, producao["maquina"] está sempre preenchido —
        esta função mantém-se por compatibilidade e para o raro caso de um
        dict construído à mão sem passar pela BD (ex: em testes)."""
        if id_para_nome is None:
            id_para_nome = {}
        nome = producao.get("maquina")
        if nome:
            return nome
        mid = str(producao.get("id_maquina", ""))
        if mid in id_para_nome:
            return id_para_nome[mid]
        if mid in ProducaoService._LEGACY_MAQUINAS:
            return ProducaoService._LEGACY_MAQUINAS[mid]
        if mid.isdigit():
            return f"Desconhecida (ID antigo: {mid})"
        return mid

    @staticmethod
    def normalizar_tempo(producao: dict) -> str:
        """Devolve o tempo da produção normalizado para HH:MM."""
        raw = (
            producao.get("tempo_real") or
            producao.get("tempo_estimado") or
            producao.get("hora_maquina") or
            producao.get("tempo") or
            ""
        )
        if not raw:
            return "00:00"
        horas = ProducaoService.converter_para_horas(str(raw))
        return ProducaoService.converter_para_string(horas)

    # ── Acesso a dados (SQLite) ─────────────────────────────────────────────

    @staticmethod
    def _montar_dict(con, row) -> dict:
        """Reconstrói o dict completo de uma produção a partir da linha da
        tabela + das relações N:N + das colunas JSON — na mesma forma que
        o resto da aplicação já espera receber."""
        d = dict(row)
        pid = d["id"]

        vinculos = con.execute(
            "SELECT pedido_id FROM producao_pedidos WHERE producao_id = ? ORDER BY pedido_id",
            (pid,),
        ).fetchall()
        d["pedidos_vinculados"] = [v["pedido_id"] for v in vinculos]

        acoes = con.execute(
            "SELECT act FROM producao_acoes_aplicadas WHERE producao_id = ? ORDER BY act",
            (pid,),
        ).fetchall()
        d["acoes_aplicadas"] = [a["act"] for a in acoes]

        try:
            d["checklist_seguranca"] = json.loads(d.get("checklist_seguranca") or "{}")
        except (TypeError, json.JSONDecodeError):
            d["checklist_seguranca"] = {}
        try:
            d["controlo_qualidade"] = json.loads(d.get("controlo_qualidade") or "{}")
        except (TypeError, json.JSONDecodeError):
            d["controlo_qualidade"] = {}

        d["nc_codigo"] = d.get("nc_codigo") or ""

        # Legacy: só expõe nr_projeto/material planos se não há pedidos
        # vinculados — é o mesmo critério que a UI já usava para decidir
        # entre o caminho novo (N:N) e o caminho antigo (campos diretos).
        if not d["pedidos_vinculados"]:
            if d.get("nr_projeto_legacy"):
                d["nr_projeto"] = d["nr_projeto_legacy"]
            if d.get("material_legacy"):
                d["material"] = d["material_legacy"]
        d.pop("nr_projeto_legacy", None)
        d.pop("material_legacy", None)

        # "maquina" já vem preenchido de maquina_nome — mantém id_maquina
        # também disponível por conveniência/depuração.
        d["maquina"] = d.pop("maquina_nome")
        d["id_maquina"] = d.pop("maquina_id")

        return d

    @staticmethod
    def obter_todos() -> list:
        """Retorna todas as produções ordenadas da mais recente para a mais antiga."""
        with SQLiteManager.conectar() as con:
            rows = con.execute("SELECT * FROM producoes ORDER BY id DESC").fetchall()
            return [ProducaoService._montar_dict(con, r) for r in rows]

    @staticmethod
    def obter_por_id(id_producao):
        with SQLiteManager.conectar() as con:
            row = con.execute("SELECT * FROM producoes WHERE id = ?", (id_producao,)).fetchone()
            if row is None:
                return None
            return ProducaoService._montar_dict(con, row)

    @staticmethod
    def obter_ultimo_lote_sls():
        with SQLiteManager.conectar() as con:
            row = con.execute(
                "SELECT lote_po FROM producoes WHERE lote_po IS NOT NULL AND lote_po != '' "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return row["lote_po"] if row else ""

    @staticmethod
    def criar_producao(tecnologia: str, maquina: str, tempo_estimado: str,
                        pedidos_vinculados: list, operador: str, campos_extra: dict = None):
        """Cria uma nova produção. Resolve automaticamente o maquina_id a
        partir do nome, se existir uma máquina correspondente no parque."""
        campos_extra = campos_extra or {}

        with SQLiteManager.conectar() as con:
            row_maq = con.execute("SELECT id FROM maquinas WHERE nome = ?", (maquina,)).fetchone()
            maquina_id = row_maq["id"] if row_maq else None

            cur = con.execute(
                """INSERT INTO producoes (
                    data_inicio, tecnologia, maquina_id, maquina_nome, tempo_estimado,
                    operador, estado, quantidade_consumida, checklist_seguranca,
                    altura_cuba, percentagem_po_novo, lote_po
                ) VALUES (?, ?, ?, ?, ?, ?, 'A Imprimir', ?, ?, ?, ?, ?)""",
                (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tecnologia, maquina_id, maquina,
                    tempo_estimado, operador,
                    str(campos_extra.get("quantidade_consumida", "")),
                    json.dumps(campos_extra.get("checklist_seguranca", {}), ensure_ascii=False),
                    str(campos_extra.get("altura_cuba", "")),
                    str(campos_extra.get("percentagem_po_novo", "")),
                    str(campos_extra.get("lote_po", "")),
                ),
            )
            nova_id = cur.lastrowid

            for pedido_id in pedidos_vinculados or []:
                con.execute(
                    "INSERT OR IGNORE INTO producao_pedidos (producao_id, pedido_id) VALUES (?, ?)",
                    (nova_id, pedido_id),
                )

            row = con.execute("SELECT * FROM producoes WHERE id = ?", (nova_id,)).fetchone()
            return ProducaoService._montar_dict(con, row)

    @staticmethod
    def atualizar_producao(producao_atualizada: dict):
        """Substitui os campos da produção com o mesmo id (ex: fecho de
        ordem) — incluindo as relações N:N (pedidos_vinculados, ações
        aplicadas), que são recriadas de raiz a partir do dict recebido."""
        pid = producao_atualizada.get("id")

        with SQLiteManager.conectar() as con:
            maquina_nome = producao_atualizada.get("maquina", "")
            row_maq = con.execute("SELECT id FROM maquinas WHERE nome = ?", (maquina_nome,)).fetchone()
            maquina_id = row_maq["id"] if row_maq else None

            nc_codigo = producao_atualizada.get("nc_codigo") or None

            con.execute(
                """UPDATE producoes SET
                    data_inicio=?, tecnologia=?, maquina_id=?, maquina_nome=?, tempo_estimado=?,
                    operador=?, estado=?, quantidade_consumida=?, checklist_seguranca=?,
                    altura_cuba=?, percentagem_po_novo=?, lote_po=?, tempo_real=?, quantidade_real=?,
                    verificado_por=?, data_fecho=?, controlo_qualidade=?, nc_codigo=?,
                    notas_acao_corretiva=?, erro=?
                   WHERE id=?""",
                (
                    producao_atualizada.get("data_inicio", ""), producao_atualizada.get("tecnologia", ""),
                    maquina_id, maquina_nome, producao_atualizada.get("tempo_estimado", ""),
                    producao_atualizada.get("operador", ""), producao_atualizada.get("estado", ""),
                    str(producao_atualizada.get("quantidade_consumida", "")),
                    json.dumps(producao_atualizada.get("checklist_seguranca", {}), ensure_ascii=False),
                    str(producao_atualizada.get("altura_cuba", "")),
                    str(producao_atualizada.get("percentagem_po_novo", "")),
                    producao_atualizada.get("lote_po", ""),
                    producao_atualizada.get("tempo_real", ""),
                    str(producao_atualizada.get("quantidade_real", "")),
                    producao_atualizada.get("verificado_por", ""),
                    producao_atualizada.get("data_fecho", ""),
                    json.dumps(producao_atualizada.get("controlo_qualidade", {}), ensure_ascii=False),
                    nc_codigo,
                    producao_atualizada.get("notas_acao_corretiva", ""),
                    producao_atualizada.get("erro", ""),
                    pid,
                ),
            )

            con.execute("DELETE FROM producao_pedidos WHERE producao_id = ?", (pid,))
            for pedido_id in producao_atualizada.get("pedidos_vinculados", []) or []:
                con.execute(
                    "INSERT OR IGNORE INTO producao_pedidos (producao_id, pedido_id) VALUES (?, ?)",
                    (pid, pedido_id),
                )

            con.execute("DELETE FROM producao_acoes_aplicadas WHERE producao_id = ?", (pid,))
            for act_cod in producao_atualizada.get("acoes_aplicadas", []) or []:
                con.execute(
                    "INSERT OR IGNORE INTO producao_acoes_aplicadas (producao_id, act) VALUES (?, ?)",
                    (pid, act_cod),
                )

            row = con.execute("SELECT * FROM producoes WHERE id = ?", (pid,)).fetchone()
            return ProducaoService._montar_dict(con, row)

    @staticmethod
    def clonar_producao(id_origem):
        """Duplica uma produção existente com um novo ID, a recomeçar em
        'Em Andamento' e sem os dados reais de fecho da ordem original.
        Retorna o novo registo, ou None se `id_origem` não existir."""
        with SQLiteManager.conectar() as con:
            origem = con.execute("SELECT * FROM producoes WHERE id = ?", (id_origem,)).fetchone()
            if origem is None:
                return None
            origem = dict(origem)

            cur = con.execute(
                """INSERT INTO producoes (
                    data_inicio, tecnologia, maquina_id, maquina_nome, tempo_estimado,
                    operador, estado, quantidade_consumida, checklist_seguranca,
                    altura_cuba, percentagem_po_novo, lote_po, erro
                ) VALUES (?, ?, ?, ?, ?, ?, 'Em Andamento', ?, ?, ?, ?, ?, '')""",
                (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), origem["tecnologia"],
                    origem["maquina_id"], origem["maquina_nome"], origem["tempo_estimado"],
                    origem["operador"], origem["quantidade_consumida"], origem["checklist_seguranca"],
                    origem["altura_cuba"], origem["percentagem_po_novo"], origem["lote_po"],
                ),
            )
            novo_id = cur.lastrowid

            vinculos = con.execute(
                "SELECT pedido_id FROM producao_pedidos WHERE producao_id = ?", (id_origem,)
            ).fetchall()
            for v in vinculos:
                con.execute(
                    "INSERT OR IGNORE INTO producao_pedidos (producao_id, pedido_id) VALUES (?, ?)",
                    (novo_id, v["pedido_id"]),
                )

            row = con.execute("SELECT * FROM producoes WHERE id = ?", (novo_id,)).fetchone()
            return ProducaoService._montar_dict(con, row)

    @staticmethod
    def remover_producao(id_producao):
        """Remove a produção do histórico pelo ID. As relações N:N são
        removidas em cascata automaticamente (ON DELETE CASCADE)."""
        with SQLiteManager.conectar() as con:
            con.execute("DELETE FROM producoes WHERE id = ?", (id_producao,))
