from database.sqlite_manager import SQLiteManager
from gui.app import AppIndustrialI3D

if __name__ == "__main__":
    # Garante que as tabelas existem antes de qualquer service tentar
    # ler/escrever — idempotente, seguro correr em todos os arranques.
    # Sem isto, a app rebenta com "no such table" em instalações novas
    # ou sempre que alguém atualiza o código sem correr a migração antes.
    SQLiteManager.garantir_esquema()

    app = AppIndustrialI3D()
    app.mainloop()