"""
migrar_json_para_sqlite.py — importa os 9 ficheiros JSON existentes para
a nova base de dados SQLite, aplicando TODA a normalização de dados
legacy (id_maquina→nome, hora_maquina→tempo_estimado, campos planos→JSON,
etc.) UMA ÚNICA VEZ nesta migração.

Depois deste script correr com sucesso, a aplicação nunca mais precisa de
"adivinhar" nomes de campo antigos — os dados na BD já estão sempre no
formato atual.

Corre com:  python scripts/migrar_json_para_sqlite.py
Idempotente-ish: pode voltar a correr contra uma BD vazia sem problema;
correr contra uma BD já populada duplica os dados (usar --limpar para
apagar as tabelas antes de importar de novo).
"""
import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.paths import (
    ARQUIVO_LOGS, ARQUIVO_MAQUINAS, ARQUIVO_PROJETOS, ARQUIVO_MATERIAIS,
    ARQUIVO_PEDIDOS, ARQUIVO_NC_FALHAS, ARQUIVO_ACOES, ARQUIVO_TEMPLATES,
    ARQUIVO_AUDIT_LOG,
)
from database.sqlite_manager import SQLiteManager


# ── Mapeamento legacy de máquinas — mesmo dicionário que existia em
# ProducaoService._LEGACY_MAQUINAS, usado aqui só durante a importação ──
_LEGACY_MAQUINAS = {
    "X1-1": "Bambu Lab X1C #1", "X1-2": "Bambu Lab X1C #2", "X1-3": "Bambu Lab X1C #3",
    "P1-1": "Bambu Lab P1S #1", "P1-2": "Bambu Lab P1S #2",
    "Form3L": "Formlabs Form 3L", "SLS-380": "3D Systems SLS 380",
}


def _carregar_json(caminho: str) -> list:
    if not os.path.exists(caminho):
        return []
    with open(caminho, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print(f"  ⚠ {caminho} tem JSON inválido — ignorado")
            return []


def _converter_horas_legacy(raw: str) -> float:
    """Reimplementação standalone de ProducaoService.converter_para_horas
    — este script não deve depender dos services (que passarão a ler da
    BD), por isso a lógica de parsing de tempo fica duplicada aqui só
    para esta migração pontual."""
    try:
        s = str(raw).strip()
        dias = 0
        if "day" in s:
            partes = s.split(", ", 1)
            dias = int(partes[0].split()[0])
            s = partes[1] if len(partes) > 1 else "0:00"
        partes = s.split(":")
        h = int(partes[0])
        m = int(partes[1]) if len(partes) > 1 else 0
        return dias * 24 + h + m / 60
    except (ValueError, TypeError, IndexError):
        return 0.0


def _horas_para_string(horas: float) -> str:
    h = int(horas)
    m = int(round((horas - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h:02d}:{m:02d}"


def _normalizar_tempo_legacy(prod: dict) -> str:
    raw = (prod.get("tempo_estimado") or prod.get("hora_maquina")
           or prod.get("tempo") or "")
    if not raw:
        return "00:00"
    return _horas_para_string(_converter_horas_legacy(str(raw)))


# ── Importadores por tabela, na ordem certa (catálogos antes de quem os referencia) ──

def migrar_maquinas(con) -> dict:
    dados = _carregar_json(ARQUIVO_MAQUINAS)
    for m in dados:
        con.execute(
            "INSERT OR REPLACE INTO maquinas (id, nome, tech, estado, manutencao, url_img) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (m.get("id"), m.get("nome", ""), m.get("tech", "FDM"),
             m.get("estado", "Operacional"), m.get("manutencao", "OK"), m.get("url_img", "")),
        )
    print(f"  ✓ {len(dados)} máquina(s)")
    return {m.get("id"): m.get("nome") for m in dados}


def migrar_projetos(con):
    dados = _carregar_json(ARQUIVO_PROJETOS)
    for p in dados:
        con.execute(
            "INSERT OR REPLACE INTO projetos (id, nome, ativo) VALUES (?, ?, ?)",
            (p.get("id"), p.get("nome", ""), 1 if p.get("ativo", True) else 0),
        )
    print(f"  ✓ {len(dados)} projeto(s)")


def migrar_materiais(con):
    dados = _carregar_json(ARQUIVO_MATERIAIS)
    for m in dados:
        con.execute(
            "INSERT OR IGNORE INTO materiais (nome, fabricante, ativo) VALUES (?, ?, ?)",
            (m.get("nome", ""), m.get("fabricante", ""), 1 if m.get("ativo", True) else 0),
        )
    print(f"  ✓ {len(dados)} material(is)")


def migrar_nc_falhas(con):
    dados = _carregar_json(ARQUIVO_NC_FALHAS)
    for nc in dados:
        con.execute(
            "INSERT OR REPLACE INTO nc_falhas (cod, descricao, categoria, tecnologia, impacto) "
            "VALUES (?, ?, ?, ?, ?)",
            (nc.get("cod"), nc.get("descricao", ""), nc.get("categoria", ""),
             nc.get("tecnologia", ""), nc.get("impacto", "")),
        )
    print(f"  ✓ {len(dados)} código(s) de não-conformidade")


def migrar_acoes_corretivas(con):
    dados = _carregar_json(ARQUIVO_ACOES)
    for a in dados:
        con.execute(
            "INSERT OR REPLACE INTO acoes_corretivas (act, acao, tecnologia, etapas) VALUES (?, ?, ?, ?)",
            (a.get("act"), a.get("acao", ""), a.get("tecnologia", ""),
             json.dumps(a.get("etapas", []), ensure_ascii=False)),
        )
        for cod in a.get("codigos_aplicaveis", []):
            con.execute(
                "INSERT OR IGNORE INTO acoes_codigos_aplicaveis (act, nc_cod) VALUES (?, ?)",
                (a.get("act"), cod),
            )
    print(f"  ✓ {len(dados)} ação(ões) corretiva(s)")


def migrar_pedidos(con) -> dict:
    dados = _carregar_json(ARQUIVO_PEDIDOS)
    id_antigo_para_novo = {}
    for p in dados:
        cur = con.execute(
            "INSERT INTO pedidos (requerente_email, nr_projeto, nome_projeto, tecnologia, "
            "data_pedido, data_entrega, link_arquivos, observacoes, estado, data_atualizacao) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (p.get("requerente_email", ""), p.get("nr_projeto", ""), p.get("nome_projeto", ""),
             p.get("tecnologia", ""), p.get("data_pedido", ""), p.get("data_entrega", ""),
             p.get("link_arquivos", ""), p.get("observacoes", ""),
             p.get("estado", "Em Andamento"), p.get("data_atualizacao", "")),
        )
        novo_id = cur.lastrowid
        id_antigo_para_novo[p.get("id")] = novo_id

        for ordem, peca in enumerate(p.get("pecas", [])):
            con.execute(
                "INSERT INTO pedido_pecas (pedido_id, pn, material, qtd_solicitada, qtd_produzida, ordem) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (novo_id, peca.get("pn", ""), peca.get("material", ""),
                 peca.get("qtd_solicitada", 0), peca.get("qtd_produzida", 0), ordem),
            )
    print(f"  ✓ {len(dados)} pedido(s)")
    return id_antigo_para_novo


def migrar_producoes(con, lookup_maquinas: dict, id_pedidos_antigo_para_novo: dict):
    dados = _carregar_json(ARQUIVO_LOGS)
    avisos = []

    for p in dados:
        # ── Resolve máquina: novo campo "maquina" > lookup parque > legacy estático ──
        maquina_nome = p.get("maquina")
        maquina_id = None
        id_bruto = str(p.get("id_maquina", ""))
        if not maquina_nome and id_bruto:
            maquina_nome = lookup_maquinas.get(id_bruto) or _LEGACY_MAQUINAS.get(id_bruto)
            if maquina_nome:
                maquina_id = id_bruto if id_bruto in lookup_maquinas else None
        elif maquina_nome:
            # tenta encontrar o id correspondente para ligar a FK
            for mid, nome in lookup_maquinas.items():
                if nome == maquina_nome:
                    maquina_id = mid
                    break
        if not maquina_nome:
            maquina_nome = f"Desconhecida (ID antigo: {id_bruto})" if id_bruto.isdigit() else (id_bruto or "N/A")
            avisos.append(f"produção {p.get('id')}: máquina não resolvida ({id_bruto!r})")

        # ── Resolve tempo estimado legacy ──
        tempo_estimado = _normalizar_tempo_legacy(p)

        # ── Resolve operador legacy ──
        operador = p.get("operador") or p.get("responsavel", "")

        # ── Resolve quantidade legacy ──
        quantidade_consumida = str(
            p.get("quantidade_consumida") or p.get("quantidade") or ""
        )

        # ── Controlo de qualidade: estrutura nova ou campos planos legacy ──
        qa = p.get("controlo_qualidade")
        if not qa:
            qa = {
                "inspecao_visual": p.get("inspecao_visual", False),
                "controlo_dimensional": p.get("controlo_dimensional", False),
                "conformidade": p.get("conformidade_peca", False),
            }

        nc_codigo = p.get("nc_codigo") or None  # "" vira NULL (ver nota no schema.sql)

        cur = con.execute(
            """INSERT INTO producoes (
                data_inicio, tecnologia, maquina_id, maquina_nome, tempo_estimado,
                operador, estado, quantidade_consumida, checklist_seguranca,
                altura_cuba, percentagem_po_novo, lote_po, tempo_real, quantidade_real,
                verificado_por, data_fecho, controlo_qualidade, nc_codigo,
                notas_acao_corretiva, erro
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                p.get("data_inicio", ""), p.get("tecnologia", "FDM"), maquina_id, maquina_nome,
                tempo_estimado, operador, p.get("estado", "Em Andamento"), quantidade_consumida,
                json.dumps(p.get("checklist_seguranca", {}), ensure_ascii=False),
                str(p.get("altura_cuba", "")), str(p.get("percentagem_po_novo", "")),
                p.get("lote_po", ""), p.get("tempo_real", ""), str(p.get("quantidade_real", "")),
                p.get("verificado_por", ""), p.get("data_fecho", ""),
                json.dumps(qa, ensure_ascii=False), nc_codigo,
                p.get("notas_acao_corretiva", ""), p.get("erro", ""),
            ),
        )
        nova_producao_id = cur.lastrowid

        # ── N:N pedidos vinculados (resolve IDs antigos para os novos) ──
        for vid in p.get("pedidos_vinculados", []):
            try:
                novo_pid = id_pedidos_antigo_para_novo.get(int(vid))
            except (TypeError, ValueError):
                novo_pid = None
            if novo_pid:
                con.execute(
                    "INSERT OR IGNORE INTO producao_pedidos (producao_id, pedido_id) VALUES (?, ?)",
                    (nova_producao_id, novo_pid),
                )

        # ── N:N ações aplicadas (loop CAPA) ──
        for act_cod in p.get("acoes_aplicadas", []):
            con.execute(
                "INSERT OR IGNORE INTO producao_acoes_aplicadas (producao_id, act) VALUES (?, ?)",
                (nova_producao_id, act_cod),
            )

    print(f"  ✓ {len(dados)} produção(ões)")
    if avisos:
        print(f"  ⚠ {len(avisos)} aviso(s) de máquina não resolvida:")
        for a in avisos[:10]:
            print(f"      - {a}")
        if len(avisos) > 10:
            print(f"      ... e mais {len(avisos) - 10}")


def migrar_templates(con):
    dados = _carregar_json(ARQUIVO_TEMPLATES)
    for t in dados:
        con.execute(
            """INSERT INTO templates_producao (
                nome, tecnologia, id_maquina, tempo_estimado, material, altura_cuba,
                percentagem_po, nr_projeto, nome_projeto, criado_em, uso_count, ultimo_uso
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (t.get("nome", ""), t.get("tecnologia", ""), t.get("id_maquina", ""),
             t.get("tempo_estimado", ""), t.get("material", ""), t.get("altura_cuba", ""),
             t.get("percentagem_po", ""), t.get("nr_projeto", ""), t.get("nome_projeto", ""),
             t.get("criado_em", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
             t.get("uso_count", 0), t.get("ultimo_uso", "")),
        )
    print(f"  ✓ {len(dados)} template(s)")


def migrar_audit_log(con):
    dados = _carregar_json(ARQUIVO_AUDIT_LOG)
    for e in dados:
        def _serializar(v):
            if isinstance(v, (list, dict)):
                return json.dumps(v, ensure_ascii=False)
            return str(v) if v is not None else None

        con.execute(
            "INSERT INTO audit_log (timestamp, utilizador, entidade, id_entidade, campo, "
            "valor_anterior, valor_novo) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (e.get("timestamp", ""), e.get("utilizador", ""), e.get("entidade", ""),
             str(e.get("id_entidade", "")), e.get("campo", ""),
             _serializar(e.get("valor_anterior")), _serializar(e.get("valor_novo"))),
        )
    print(f"  ✓ {len(dados)} entrada(s) de auditoria")


def migrar(limpar: bool = False):
    """Lógica de migração, chamável diretamente (sem passar pela CLI) —
    é isto que os testes invocam, para não colidir com o argparse a
    tentar interpretar os argumentos do próprio pytest."""
    print("═" * 60)
    print("MIGRAÇÃO JSON → SQLite — AManager")
    print("═" * 60)

    SQLiteManager.garantir_esquema()

    with SQLiteManager.conectar() as con:
        if limpar:
            print("\n🗑  A limpar tabelas existentes...")
            for tabela in ["producao_acoes_aplicadas", "producao_pedidos", "producoes",
                           "pedido_pecas", "pedidos", "acoes_codigos_aplicaveis",
                           "acoes_corretivas", "nc_falhas", "materiais", "projetos",
                           "maquinas", "templates_producao", "audit_log"]:
                con.execute(f"DELETE FROM {tabela}")
            print("  ✓ Tabelas limpas")

        print("\n📦 A importar catálogos...")
        lookup_maquinas = migrar_maquinas(con)
        migrar_projetos(con)
        migrar_materiais(con)
        migrar_nc_falhas(con)
        migrar_acoes_corretivas(con)

        print("\n📦 A importar pedidos...")
        id_pedidos = migrar_pedidos(con)

        print("\n📦 A importar produções (com normalização legacy)...")
        migrar_producoes(con, lookup_maquinas, id_pedidos)

        print("\n📦 A importar templates e auditoria...")
        migrar_templates(con)
        migrar_audit_log(con)

    print("\n" + "═" * 60)
    print("MIGRAÇÃO CONCLUÍDA COM SUCESSO")
    print("═" * 60)


def main():
    """Ponto de entrada da linha de comandos — só aqui se lê sys.argv."""
    parser = argparse.ArgumentParser(description="Migra os dados JSON do AManager para SQLite.")
    parser.add_argument("--limpar", action="store_true",
                        help="Apaga todas as tabelas antes de importar (evita duplicados ao re-correr).")
    args = parser.parse_args()
    migrar(limpar=args.limpar)


if __name__ == "__main__":
    main()
