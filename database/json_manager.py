import json
import os
import time

class JSONManager:
    @staticmethod
    def _adquirir_lock(caminho, timeout=5):
        """Cria o ficheiro de lock de forma atómica (O_EXCL), evitando a condição de
        corrida de verificar 'existe?' e criar como dois passos separados."""
        lock_file = caminho + ".lock"
        start_time = time.time()

        while True:
            try:
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return
            except FileExistsError:
                if time.time() - start_time > timeout:
                    try:
                        os.remove(lock_file)  # Quebra lock preso (ex: processo morreu a meio)
                    except OSError:
                        pass
                    start_time = time.time()  # Reinicia o timer para evitar loop de roubo imediato
                time.sleep(0.1)

    @staticmethod
    def _libertar_lock(caminho):
        lock_file = caminho + ".lock"
        try:
            os.remove(lock_file)
        except OSError:
            pass

    @staticmethod
    def _ler_sem_lock(caminho):
        if not os.path.exists(caminho):
            return []
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            corrompido = caminho + ".corrompido"
            try:
                os.replace(caminho, corrompido)
            except OSError:
                pass
            print(f"[JSONManager] AVISO: '{caminho}' estava corrompido e foi movido para "
                  f"'{corrompido}' para não perder o conteúdo. A continuar com dados vazios. "
                  f"Detalhe: {e}")
            return []

    @staticmethod
    def _escrever_sem_lock(dados, caminho):
        """Escrita atómica: grava num ficheiro temporário e só depois substitui o
        original, para nunca deixar um JSON truncado/inválido em disco."""
        pasta = os.path.dirname(caminho) or "."
        os.makedirs(pasta, exist_ok=True)
        tmp_path = caminho + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, caminho)

    @staticmethod
    def carregar(caminho):
        JSONManager._adquirir_lock(caminho)
        try:
            return JSONManager._ler_sem_lock(caminho)
        finally:
            JSONManager._libertar_lock(caminho)

    @staticmethod
    def salvar(dados, caminho):
        JSONManager._adquirir_lock(caminho)
        try:
            JSONManager._escrever_sem_lock(dados, caminho)
        finally:
            JSONManager._libertar_lock(caminho)

    @staticmethod
    def atualizar(caminho, transformar):
        """Lê, aplica `transformar(dados) -> dados_novos` e grava, tudo sob um único
        ciclo de lock — para operações de leitura-modificação-escrita (ex: atualizar
        um registo existente) não ficarem expostas a outra escrita a meio."""
        JSONManager._adquirir_lock(caminho)
        try:
            dados = JSONManager._ler_sem_lock(caminho)
            dados = transformar(dados)
            JSONManager._escrever_sem_lock(dados, caminho)
            return dados
        finally:
            JSONManager._libertar_lock(caminho)
