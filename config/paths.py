import os
import sys

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Sobe um nível para a raiz

BASE_DIR = get_base_path()
DATA_DIR = os.path.join(BASE_DIR, "data")

# Garantir que a pasta data existe
os.makedirs(DATA_DIR, exist_ok=True)

ARQUIVO_LOGS = os.path.join(DATA_DIR, "producao_i3D.json")
ARQUIVO_MAQUINAS = os.path.join(DATA_DIR, "parque_maquinas.json")
ARQUIVO_PROJETOS = os.path.join(DATA_DIR, "projetos.json")
ARQUIVO_MATERIAIS = os.path.join(DATA_DIR, "materiais.json")
ARQUIVO_PEDIDOS = os.path.join(DATA_DIR, "pedidos.json")