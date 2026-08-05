import re

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
        """Converte string 'HH:MM' para float (ex: '01:30' -> 1.5)"""
        try:
            partes = hhmm.split(':')
            if len(partes) >= 2:
                return int(partes[0]) + (int(partes[1]) / 60)
            return 0.0
        except ValueError:
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
    def obter_ultimo_lote_sls():
        from database.json_manager import JSONManager
        from config.paths import ARQUIVO_LOGS
        
        logs = JSONManager.carregar(ARQUIVO_LOGS)
        # Filtra apenas registos que tenham a chave "lote_po" preenchida, do mais recente para o mais antigo
        for log in reversed(logs):
            if log.get("lote_po"):
                return log.get("lote_po")
        return "" # Retorna vazio se for a primeira vez