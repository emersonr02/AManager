# -*- mode: python ; coding: utf-8 -*-
"""Executável do AManager para a pasta partilhada da rede.

    pip install pyinstaller
    python -m PyInstaller AManager.spec --noconfirm

Gera dist/AManager.exe: um só ficheiro, sem consola. Vai para a pasta da rede
AO LADO da pasta data/ (é essa a base de dados que usa) — nunca copiar o data/
do repositório. Passos completos no README ("Executável para a rede").
"""
import glob
import os
import subprocess
from datetime import datetime

from PyInstaller.utils.hooks import collect_data_files

RAIZ = os.path.abspath(SPECPATH)


def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


# Versão no título da janela: data do build + commit (com "+local" se havia
# alterações por fazer commit — esse executável não corresponde a nenhum commit).
commit = _git("rev-parse", "--short", "HEAD") or "sem-git"
alterado = bool(_git("status", "--porcelain", "--untracked-files=no"))
versao = f"{datetime.now():%Y.%m.%d} ({commit}{'+local' if alterado else ''})"
if alterado:
    print("\nAVISO: há alterações por fazer commit; o executável não corresponde a um commit.\n")
os.makedirs(os.path.join(RAIZ, "build"), exist_ok=True)
ficheiro_versao = os.path.join(RAIZ, "build", "versao.txt")
with open(ficheiro_versao, "w", encoding="utf-8") as f:
    f.write(versao)

# As tabs são importadas pelo nome (importlib, em gui/app.py): o PyInstaller
# não as deteta sozinho, por isso entram todos os módulos de gui/ explicitamente.
modulos_gui = sorted(
    os.path.relpath(caminho, RAIZ)[:-3].replace(os.sep, ".")
    for caminho in glob.glob(os.path.join(RAIZ, "gui", "**", "*.py"), recursive=True)
    if not caminho.endswith("__init__.py"))

# Ícone do .exe: logo_ceiia.ico na raiz do repositório, se existir (a janela
# usa o logo_ceiia.ico que estiver ao lado do .exe na rede).
icone = os.path.join(RAIZ, "logo_ceiia.ico")

a = Analysis(
    [os.path.join(RAIZ, "main.py")],
    pathex=[RAIZ],
    datas=collect_data_files("customtkinter") + [(ficheiro_versao, ".")],
    hiddenimports=modulos_gui,
    excludes=["pytest", "_pytest", "tests", "IPython", "jupyter_client", "notebook",
              "PyQt5", "PyQt6", "PySide2", "PySide6"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AManager",
    console=False,
    upx=False,   # UPX faz os antivírus desconfiarem do .exe
    icon=icone if os.path.exists(icone) else None,
)
