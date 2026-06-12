import csv

class ExportService:
    
    @staticmethod
    def exportar_historico_csv(caminho_salvar: str, dados_principais: list, 
                               consumo_materiais: dict, horas_maquinas: dict) -> bool:
        """
        Gera o ficheiro CSV de exportação com os dados e os resumos de Pareto.
        Retorna True se for bem sucedido, False caso contrário.
        """
        from services.producao_service import ProducaoService # Import local para evitar dependência circular

        try:
            with open(caminho_salvar, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                
                # Tabela Principal
                writer.writerow(["ID", "DATA", "PROJETO", "MAQUINA", "MATERIAL", "QUANTIDADE", "TEMPO", "ESTADO"])
                writer.writerows(dados_principais)
                
                writer.writerow([])
                writer.writerow([])
                
                # Resumo de Materiais
                writer.writerow(["RESUMO POR MATERIAL", "QUANTIDADE TOTAL"])
                for mat, tot in consumo_materiais.items(): 
                    writer.writerow([mat, f"{tot:.2f}"])
                
                writer.writerow([])
                
                # Resumo de Máquinas
                writer.writerow(["RESUMO POR MÁQUINA", "HORAS TOTAIS"])
                for maq, tot_h in horas_maquinas.items(): 
                    tempo_formatado = ProducaoService.converter_para_string(tot_h)
                    writer.writerow([maq, tempo_formatado])
                    
            return True
        except Exception as e:
            print(f"Erro na exportação CSV: {e}")
            return False