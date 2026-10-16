import os
import sys


def obter_versao() -> str:
    """Versão do executável (data do build e commit), gravada em versao.txt pelo
    AManager.spec. A correr a partir do código não há versão: devolve ""."""
    pasta = getattr(sys, "_MEIPASS", None)
    if not pasta:
        return ""
    try:
        with open(os.path.join(pasta, "versao.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""
