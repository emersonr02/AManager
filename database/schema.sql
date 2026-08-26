-- ═══════════════════════════════════════════════════════════════════════
-- AManager — Esquema SQLite
-- ═══════════════════════════════════════════════════════════════════════
-- Substitui os 9 ficheiros JSON por uma única base de dados relacional.
-- Ver database/sqlite_manager.py para a lógica de ligação e migrações.

PRAGMA foreign_keys = ON;

-- ── CATÁLOGOS (dados de referência, poucas linhas, editados raramente) ──

CREATE TABLE IF NOT EXISTS maquinas (
    id          TEXT PRIMARY KEY,
    nome        TEXT NOT NULL,
    tech        TEXT NOT NULL,
    estado      TEXT NOT NULL DEFAULT 'Operacional',
    manutencao  TEXT NOT NULL DEFAULT 'OK',
    url_img     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS projetos (
    id      TEXT PRIMARY KEY,
    nome    TEXT NOT NULL DEFAULT '',
    ativo   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS materiais (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT NOT NULL,
    fabricante  TEXT NOT NULL DEFAULT '',
    ativo       INTEGER NOT NULL DEFAULT 1,
    UNIQUE (nome, fabricante)
);

CREATE TABLE IF NOT EXISTS nc_falhas (
    cod         TEXT PRIMARY KEY,
    descricao   TEXT NOT NULL,
    categoria   TEXT NOT NULL DEFAULT '',
    tecnologia  TEXT NOT NULL,
    impacto     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS acoes_corretivas (
    act         TEXT PRIMARY KEY,
    acao        TEXT NOT NULL,
    tecnologia  TEXT NOT NULL,
    etapas      TEXT NOT NULL DEFAULT '[]'  -- JSON array; lista ordenada, pequena, sem valor em normalizar
);

-- N:N — quais códigos NC uma ação corretiva resolve
CREATE TABLE IF NOT EXISTS acoes_codigos_aplicaveis (
    act     TEXT NOT NULL REFERENCES acoes_corretivas(act) ON DELETE CASCADE,
    nc_cod  TEXT NOT NULL REFERENCES nc_falhas(cod) ON DELETE CASCADE,
    PRIMARY KEY (act, nc_cod)
);

-- ── PEDIDOS ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pedidos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    requerente_email    TEXT NOT NULL,
    nr_projeto          TEXT NOT NULL DEFAULT '',
    nome_projeto        TEXT NOT NULL DEFAULT '',
    tecnologia          TEXT NOT NULL DEFAULT '',
    data_pedido         TEXT NOT NULL,
    data_entrega        TEXT NOT NULL,
    link_arquivos       TEXT NOT NULL DEFAULT '',
    observacoes         TEXT NOT NULL DEFAULT '',
    estado              TEXT NOT NULL DEFAULT 'Em Andamento',
    ativo               INTEGER NOT NULL DEFAULT 1,
    data_atualizacao    TEXT NOT NULL
);

-- 1:N — peças de um pedido (antes era uma lista embutida no JSON)
CREATE TABLE IF NOT EXISTS pedido_pecas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id       INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    pn              TEXT NOT NULL,
    material        TEXT NOT NULL DEFAULT '',
    qtd_solicitada  INTEGER NOT NULL DEFAULT 0,
    qtd_produzida   INTEGER NOT NULL DEFAULT 0,
    ordem           INTEGER NOT NULL DEFAULT 0   -- preserva a ordem de introdução
);

-- ── PRODUÇÕES ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS producoes (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    data_inicio             TEXT NOT NULL,
    tecnologia              TEXT NOT NULL,

    -- maquina_id referencia o catálogo; maquina_nome é um SNAPSHOT do nome
    -- no momento da criação — se a máquina for renomeada ou removida depois,
    -- o histórico continua a mostrar o nome que tinha então (mesma filosofia
    -- que já usávamos em normalizar_maquina, agora persistida em vez de
    -- recalculada em runtime).
    maquina_id              TEXT REFERENCES maquinas(id) ON DELETE SET NULL,
    maquina_nome            TEXT NOT NULL,

    tempo_estimado          TEXT NOT NULL DEFAULT '00:00',
    operador                TEXT NOT NULL DEFAULT '',
    estado                  TEXT NOT NULL DEFAULT 'Em Andamento',
    quantidade_consumida    TEXT NOT NULL DEFAULT '',

    checklist_seguranca     TEXT NOT NULL DEFAULT '{}',  -- JSON: forma varia por tecnologia
    altura_cuba             TEXT NOT NULL DEFAULT '',
    percentagem_po_novo     TEXT NOT NULL DEFAULT '',
    lote_po                 TEXT NOT NULL DEFAULT '',

    tempo_real              TEXT NOT NULL DEFAULT '',
    quantidade_real         TEXT NOT NULL DEFAULT '',
    verificado_por          TEXT NOT NULL DEFAULT '',
    data_fecho              TEXT NOT NULL DEFAULT '',
    controlo_qualidade      TEXT NOT NULL DEFAULT '{}',  -- JSON: {"inspecao_visual":bool,...}

    -- nc_codigo é NULL quando não há não-conformidade. Uma FK não permite
    -- DEFAULT '' aqui: '' teria de existir como linha em nc_falhas para não
    -- violar a constraint. NULL é o valor correto para "não aplicável" e
    -- fica automaticamente isento da verificação de FK pelo SQLite.
    nc_codigo               TEXT REFERENCES nc_falhas(cod) ON DELETE SET NULL,
    notas_acao_corretiva    TEXT NOT NULL DEFAULT '',
    erro                    TEXT NOT NULL DEFAULT '',

    -- Produções muito antigas guardavam projeto/material diretamente,
    -- sem ligação a um pedido (o conceito de "pedido" ainda não existia).
    -- Preserva-se aqui para não perder histórico na migração; o service
    -- devolve estes valores nas mesmas chaves que o JSON legacy usava
    -- ("nr_projeto"/"material") só quando não há pedidos_vinculados.
    nr_projeto_legacy       TEXT NOT NULL DEFAULT '',
    material_legacy         TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_producoes_data_inicio ON producoes(data_inicio);
CREATE INDEX IF NOT EXISTS idx_producoes_estado ON producoes(estado);
CREATE INDEX IF NOT EXISTS idx_producoes_maquina_id ON producoes(maquina_id);
CREATE INDEX IF NOT EXISTS idx_producoes_nc_codigo ON producoes(nc_codigo);

-- N:N — produção <-> pedidos vinculados (antes: lista de IDs em JSON,
-- com bugs de tipo int/str que já corrigimos manualmente várias vezes)
CREATE TABLE IF NOT EXISTS producao_pedidos (
    producao_id INTEGER NOT NULL REFERENCES producoes(id) ON DELETE CASCADE,
    pedido_id   INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    PRIMARY KEY (producao_id, pedido_id)
);

-- N:N — ações corretivas confirmadas como aplicadas numa produção (loop CAPA)
CREATE TABLE IF NOT EXISTS producao_acoes_aplicadas (
    producao_id INTEGER NOT NULL REFERENCES producoes(id) ON DELETE CASCADE,
    act         TEXT NOT NULL REFERENCES acoes_corretivas(act) ON DELETE CASCADE,
    PRIMARY KEY (producao_id, act)
);

-- ── TEMPLATES DE PRODUÇÃO ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS templates_producao (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                TEXT NOT NULL,
    tecnologia          TEXT NOT NULL,
    id_maquina          TEXT NOT NULL DEFAULT '',
    tempo_estimado      TEXT NOT NULL DEFAULT '',
    material            TEXT NOT NULL DEFAULT '',
    altura_cuba         TEXT NOT NULL DEFAULT '',
    percentagem_po      TEXT NOT NULL DEFAULT '',
    nr_projeto          TEXT NOT NULL DEFAULT '',
    nome_projeto        TEXT NOT NULL DEFAULT '',
    criado_em           TEXT NOT NULL,
    uso_count           INTEGER NOT NULL DEFAULT 0,
    ultimo_uso          TEXT NOT NULL DEFAULT ''
);

-- ── TRILHA DE AUDITORIA (append-only) ──────────────────────────────────

CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    utilizador      TEXT NOT NULL,
    entidade        TEXT NOT NULL,
    id_entidade     TEXT NOT NULL,
    campo           TEXT NOT NULL,
    valor_anterior  TEXT,   -- serializado (str/JSON conforme o tipo original)
    valor_novo      TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_entidade ON audit_log(entidade, id_entidade);
