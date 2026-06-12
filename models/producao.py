from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Producao:
    id: int
    localizacao: str
    id_maquina: str
    nr_projeto: str
    data_inicio: str
    hora_maquina: str
    material: str
    quantidade: float
    tecnologia: str
    responsavel: str
    estado: str = "Em Andamento"
    altura: Optional[float] = 0.0     # Específico SLS
    perc_po: Optional[float] = 0.0    # Específico SLS
    erro: str = ""

    def to_dict(self):
        """Converte o objeto de volta para dicionário para salvar no JSON"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, dados: dict):
        """Cria um objeto Producao a partir da leitura do JSON"""
        # Filtra apenas as chaves que existem no dataclass para evitar erros
        chaves_validas = {k: v for k, v in dados.items() if k in cls.__dataclass_fields__}
        return cls(**chaves_validas)