import os
import sys

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 

BASE_DIR = get_base_path()
DATA_DIR = os.path.join(BASE_DIR, "data")


os.makedirs(DATA_DIR, exist_ok=True)

ARQUIVO_LOGS = os.path.join(DATA_DIR, "producao_i3D.json")
ARQUIVO_MAQUINAS = os.path.join(DATA_DIR, "parque_maquinas.json")
ARQUIVO_PROJETOS = os.path.join(DATA_DIR, "projetos.json")
ARQUIVO_MATERIAIS = os.path.join(DATA_DIR, "materiais.json")
ARQUIVO_PEDIDOS = "data/pedidos.json"
ARQUIVO_NC_FALHAS = "data/nc_falhas.json"
ARQUIVO_ACOES = "data/acoes_corretivas.json"
ARQUIVO_IMPRESSORAS = os.path.join(DATA_DIR, "impressoras.json") 