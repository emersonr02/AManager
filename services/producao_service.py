import re
from datetime import datetime

from database.json_manager import JSONManager
from config.paths import ARQUIVO_LOGS

class ProducaoService:

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
            # "N days, H:MM:SS" — formato timedelta do Python
            if 'day' in s:
                partes_dia = s.split(', ', 1)
                dias = int(partes_dia[0].split()[0])
                s = partes_dia[1] if len(partes_dia) > 1 else "0:00"
            partes = s.split(':')
            h = int(partes[0])
            m = int(partes[1]) if len(partes) > 1 else 0
            # segundos ignorados na precisão de minutos
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
        """
        Calcula o consumo de pó em kg.
        Os parâmetros da máquina (largura, profundidade, densidade) agora têm 
        valores por defeito, mas podem ser injetados dinamicamente no futuro.
        """
        volume_mm3 = largura_cuba * profundidade_cuba * altura_mm
        peso_total_kg = (volume_mm3 / 1_000_000) * densidade_po
        consumo_real_kg = peso_total_kg * perc_po_novo
        
        return round(consumo_real_kg, 4)

    @staticmethod
    def estimar_quantidade(producao: dict) -> str:
        """Quantidade estimada de uma produção, num formato pronto a mostrar.
        Para SLS não há um campo direto — deriva-se de altura_cuba e
        percentagem_po_novo pela mesma fórmula usada no fecho da ordem."""
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

    @staticmethod
    def obter_ultimo_lote_sls():
        logs = JSONManager.carregar(ARQUIVO_LOGS)
        # Filtra apenas registos que tenham a chave "lote_po" preenchida, do mais recente para o mais antigo
        for log in reversed(logs):
            if log.get("lote_po"):
                return log.get("lote_po")
        return "" # Retorna vazio se for a primeira vez

    @staticmethod
    def obter_todos():
        """Retorna todas as produções ordenadas da mais recente para a mais antiga."""
        producoes = JSONManager.carregar(ARQUIVO_LOGS)
        producoes.sort(key=lambda x: int(x.get("id", 0)), reverse=True)
        return producoes

    @staticmethod
    def obter_por_id(id_producao):
        for p in JSONManager.carregar(ARQUIVO_LOGS):
            if p.get("id") == id_producao:
                return p
        return None

    @staticmethod
    def criar_producao(tecnologia: str, maquina: str, tempo_estimado: str,
                        pedidos_vinculados: list, operador: str, campos_extra: dict = None):
        """Aplica a regra de negócio para gerar um novo ID e salvar uma produção.
        `campos_extra` recebe os campos específicos da tecnologia (quantidades,
        checklist de segurança, dados de SLS, etc.)."""
        nova_producao = {}

        def _transformar(producoes):
            novo_id = max([int(p.get("id", 0)) for p in producoes]) + 1 if producoes else 1
            nova_producao.update({
                "id": novo_id,
                "data_inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "tecnologia": tecnologia,
                "maquina": maquina,
                "tempo_estimado": tempo_estimado,
                "pedidos_vinculados": pedidos_vinculados,
                "estado": "A Imprimir",
                "operador": operador,
            })
            if campos_extra:
                nova_producao.update(campos_extra)
            producoes.append(nova_producao)
            return producoes

        # Lê, calcula o novo ID e grava sob um único lock, para duas produções
        # lançadas ao mesmo tempo (rede partilhada) não colidirem no mesmo ID.
        JSONManager.atualizar(ARQUIVO_LOGS, _transformar)
        return nova_producao

    @staticmethod
    def atualizar_producao(producao_atualizada: dict):
        """Substitui a produção com o mesmo id (ex: fecho de ordem)."""
        def _transformar(producoes):
            for idx, p in enumerate(producoes):
                if p.get("id") == producao_atualizada.get("id"):
                    producoes[idx] = producao_atualizada
                    break
            return producoes

        JSONManager.atualizar(ARQUIVO_LOGS, _transformar)
        return producao_atualizada

    @staticmethod
    def clonar_producao(id_origem):
        """Duplica uma produção existente com um novo ID, a recomeçar em 'Em
        Andamento' e sem os dados reais de fecho da ordem original.
        Retorna o novo registo, ou None se `id_origem` não existir."""
        clone = {}

        def _transformar(producoes):
            origem = next((p for p in producoes if p.get("id") == id_origem), None)
            if origem is None:
                return producoes

            novo = origem.copy()
            novo["id"] = max([int(p.get("id", 0)) for p in producoes]) + 1
            novo["data_inicio"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            novo["estado"] = "Em Andamento"
            novo["erro"] = ""
            # Limpa todos os dados de fecho do original — o clone começa do zero
            for campo in ("tempo_real", "quantidade_real", "verificado_por",
                          "data_fecho", "nc_codigo", "controlo_qualidade"):
                novo.pop(campo, None)

            producoes.append(novo)
            clone.update(novo)
            return producoes

        JSONManager.atualizar(ARQUIVO_LOGS, _transformar)
        return clone or None

    # Mapeamento de IDs legacy para nomes completos de maquinas
    _LEGACY_MAQUINAS = {
        "X1-1":    "Bambu Lab X1C #1",
        "X1-2":    "Bambu Lab X1C #2",
        "X1-3":    "Bambu Lab X1C #3",
        "P1-1":    "Bambu Lab P1S #1",
        "P1-2":    "Bambu Lab P1S #2",
        "Form3L":  "Formlabs Form 3L",
        "SLS-380": "3D Systems SLS 380",
    }

    @staticmethod
    def normalizar_maquina(producao: dict, id_para_nome: dict = None) -> str:
        """Resolve o nome completo da maquina de uma producao.
        Ordem: campo 'maquina' (novo) -> lookup parque -> mapeamento legacy
        -> id_maquina bruto. IDs numericos (sistema antigo) ficam assinalados."""
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
        """Devolve o tempo da producao normalizado para HH:MM.
        Tenta: tempo_real > tempo_estimado > hora_maquina > tempo.
        Converte formatos legacy ('H:MM:SS', 'N days, H:MM:SS') para HH:MM."""
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

    @staticmethod
    def remover_producao(id_producao):
        """Remove a produção do histórico local pelo ID."""
        JSONManager.atualizar(ARQUIVO_LOGS, lambda producoes: [p for p in producoes if p.get("id") != id_producao])