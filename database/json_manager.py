import json
import os
import time

class JSONManager:
    @staticmethod
    def _aguardar_lock(caminho, timeout=3):
        """Evita colisão de dados se duas pessoas salvarem ao mesmo tempo na rede."""
        lock_file = caminho + ".lock"
        start_time = time.time()
        
        while os.path.exists(lock_file):
            if time.time() - start_time > timeout:
                try: os.remove(lock_file) # Força a quebra se travar
                except: pass
                break
            time.sleep(0.1)
            
        try:
            with open(lock_file, 'w') as f: f.write("locked")
        except: pass

    @staticmethod
    def _liberar_lock(caminho):
        lock_file = caminho + ".lock"
        if os.path.exists(lock_file):
            try: os.remove(lock_file)
            except: pass

    @staticmethod
    def carregar(caminho):
        if not os.path.exists(caminho): return []
        JSONManager._aguardar_lock(caminho)
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
        finally:
            JSONManager._liberar_lock(caminho)

    @staticmethod
    def salvar(dados, caminho):
        JSONManager._aguardar_lock(caminho)
        try:
            with open(caminho, 'w', encoding='utf-8') as f:
                json.dump(dados, f, indent=2, ensure_ascii=False)
        finally:
            JSONManager._liberar_lock(caminho)