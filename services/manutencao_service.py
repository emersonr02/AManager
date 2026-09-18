from datetime import datetime

from database.json_manager import JSONManager
from config.paths import ARQUIVO_MANUTENCOES, ARQUIVO_TAREFAS_MANUTENCAO
from services.maquina_service import MaquinaService
from services.producao_service import ProducaoService

# A partir deste rácio (tempo/horas decorridos sobre a frequência definida) uma
# tarefa passa a "proxima" (aviso); a partir de 1.0 passa a "atrasada".
LIMIAR_AVISO_RATIO = 0.8


def _parse_datetime_seguro(valor):
    if not valor:
        return None
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(valor, formato)
        except ValueError:
            continue
    return None


class ManutencaoService:

    @staticmethod
    def obter_tarefas(incluir_inativas: bool = False):
        tarefas = JSONManager.carregar(ARQUIVO_TAREFAS_MANUTENCAO)
        if incluir_inativas:
            return tarefas
        return [t for t in tarefas if t.get("ativo", True)]

    @staticmethod
    def criar_tarefa(modelo: str, nome: str, frequencia_dias: int = None,
                      frequencia_horas: float = None, descricao: str = ""):
        if not frequencia_dias and not frequencia_horas:
            raise ValueError("A tarefa tem de ter pelo menos uma frequência definida (dias ou horas).")

        nova_tarefa = {}

        def _transformar(tarefas):
            novo_id = max([t.get("id", 0) for t in tarefas]) + 1 if tarefas else 1
            nova_tarefa.update({
                "id": novo_id,
                "modelo": modelo,
                "nome": nome,
                "descricao": descricao,
                "frequencia_dias": frequencia_dias,
                "frequencia_horas": frequencia_horas,
                "ativo": True,
            })
            tarefas.append(nova_tarefa)
            return tarefas

        JSONManager.atualizar(ARQUIVO_TAREFAS_MANUTENCAO, _transformar)
        return nova_tarefa

    @staticmethod
    def atualizar_tarefa(tarefa_atualizada: dict):
        if not tarefa_atualizada.get("frequencia_dias") and not tarefa_atualizada.get("frequencia_horas"):
            raise ValueError("A tarefa tem de ter pelo menos uma frequência definida (dias ou horas).")

        def _transformar(tarefas):
            return [tarefa_atualizada if t.get("id") == tarefa_atualizada.get("id") else t for t in tarefas]

        JSONManager.atualizar(ARQUIVO_TAREFAS_MANUTENCAO, _transformar)
        return tarefa_atualizada

    @staticmethod
    def definir_ativa(tarefa_id, ativa: bool):
        def _transformar(tarefas):
            for t in tarefas:
                if t.get("id") == tarefa_id:
                    t["ativo"] = ativa
            return tarefas

        JSONManager.atualizar(ARQUIVO_TAREFAS_MANUTENCAO, _transformar)

    @staticmethod
    def obter_historico(maquina_id=None, tarefa_id=None):
        """Histórico de manutenções concluídas, da mais recente para a mais antiga."""
        historico = JSONManager.carregar(ARQUIVO_MANUTENCOES)
        if maquina_id is not None:
            historico = [h for h in historico if h.get("maquina_id") == maquina_id]
        if tarefa_id is not None:
            historico = [h for h in historico if h.get("tarefa_id") == tarefa_id]
        historico.sort(key=lambda h: h.get("data_realizacao", ""), reverse=True)
        return historico

    @staticmethod
    def registar_conclusao(tarefa_id, maquina_id, operador: str, notas: str = ""):
        novo_registo = {}

        def _transformar(historico):
            novo_id = max([h.get("id", 0) for h in historico]) + 1 if historico else 1
            novo_registo.update({
                "id": novo_id,
                "tarefa_id": tarefa_id,
                "maquina_id": maquina_id,
                "data_realizacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "operador": operador,
                "notas": notas,
            })
            historico.append(novo_registo)
            return historico

        JSONManager.atualizar(ARQUIVO_MANUTENCOES, _transformar)
        return novo_registo

    @staticmethod
    def calcular_proximas_tarefas():
        """Junta máquinas + tarefas periódicas (por modelo) + histórico + produções
        para determinar o estado de cada par (máquina, tarefa): atrasada, próxima,
        ok, ou sem_dados (máquina sem produções registadas, não há como estimar).

        Devolve uma lista ordenada por urgência (atrasadas primeiro), usada tanto
        pela agenda de Manutenção como pelo resumo de alertas do Dashboard.
        """
        maquinas = [m for m in MaquinaService.obter_todas() if m.get("estado") != "Desativado"]
        tarefas = ManutencaoService.obter_tarefas(incluir_inativas=False)
        if not maquinas or not tarefas:
            return []

        historico = JSONManager.carregar(ARQUIVO_MANUTENCOES)
        producoes = ProducaoService.obter_todos()

        # Produções por máquina (identificadas pelo nome, tal como producao_i3D.json
        # já as regista — não pelo id), ordenadas por data, com as horas já convertidas.
        producoes_por_maquina = {}
        for p in producoes:
            dt = _parse_datetime_seguro(p.get("data_inicio", ""))
            if not dt:
                continue
            horas = ProducaoService.converter_para_horas(str(p.get("tempo_real") or p.get("tempo_estimado") or "00:00"))
            producoes_por_maquina.setdefault(p.get("maquina"), []).append((dt, horas))
        for lista in producoes_por_maquina.values():
            lista.sort(key=lambda par: par[0])

        # Última conclusão registada por par (tarefa, máquina).
        ultima_conclusao = {}
        for h in historico:
            chave = (h.get("tarefa_id"), h.get("maquina_id"))
            dt = _parse_datetime_seguro(h.get("data_realizacao", ""))
            if not dt:
                continue
            if chave not in ultima_conclusao or dt > ultima_conclusao[chave]:
                ultima_conclusao[chave] = dt

        agora = datetime.now()
        linhas = []

        for m in maquinas:
            modelo = m.get("modelo", "")
            if not modelo:
                continue
            tarefas_modelo = [t for t in tarefas if t.get("modelo") == modelo]
            if not tarefas_modelo:
                continue
            producoes_maquina = producoes_por_maquina.get(m.get("nome"), [])

            for t in tarefas_modelo:
                chave = (t["id"], m["id"])
                concluida_em = ultima_conclusao.get(chave)

                # Base para contar dias/horas decorridos: a última conclusão registada,
                # ou (se nunca foi concluída) a produção mais antiga da máquina — nunca
                # "atrasada imediatamente", isso pintaria toda a frota de vermelho no
                # primeiro dia em que as tarefas periódicas fossem criadas.
                base = concluida_em or (producoes_maquina[0][0] if producoes_maquina else None)

                linha = {
                    "maquina_id": m["id"],
                    "maquina_nome": m.get("nome"),
                    "modelo": modelo,
                    "tarefa_id": t["id"],
                    "tarefa_nome": t.get("nome"),
                    "ultima_conclusao": concluida_em.strftime("%Y-%m-%d") if concluida_em else None,
                }

                if base is None:
                    linha.update({
                        "dias_desde": None, "frequencia_dias": t.get("frequencia_dias"),
                        "horas_desde": None, "frequencia_horas": t.get("frequencia_horas"),
                        "ratio": None, "estado": "sem_dados",
                    })
                    linhas.append(linha)
                    continue

                dias_desde = (agora - base).days
                horas_desde = round(sum(h for (dt, h) in producoes_maquina if dt > base), 2)

                freq_dias = t.get("frequencia_dias")
                freq_horas = t.get("frequencia_horas")
                ratios = []
                if freq_dias:
                    ratios.append(dias_desde / freq_dias)
                if freq_horas:
                    ratios.append(horas_desde / freq_horas)
                ratio = max(ratios) if ratios else 0.0

                if ratio >= 1.0:
                    estado = "atrasada"
                elif ratio >= LIMIAR_AVISO_RATIO:
                    estado = "proxima"
                else:
                    estado = "ok"

                linha.update({
                    "dias_desde": dias_desde, "frequencia_dias": freq_dias,
                    "horas_desde": horas_desde, "frequencia_horas": freq_horas,
                    "ratio": round(ratio, 4), "estado": estado,
                })
                linhas.append(linha)

        ordem_estado = {"atrasada": 0, "proxima": 1, "ok": 2, "sem_dados": 3}
        linhas.sort(key=lambda l: (ordem_estado[l["estado"]], -(l["ratio"] or 0)))
        return linhas

    @staticmethod
    def contar_alertas():
        linhas = ManutencaoService.calcular_proximas_tarefas()
        return {
            "atrasadas": sum(1 for l in linhas if l["estado"] == "atrasada"),
            "proximas": sum(1 for l in linhas if l["estado"] == "proxima"),
        }
