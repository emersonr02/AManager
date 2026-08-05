from datetime import datetime
import re
import os


def processar_texto_email(self, texto):
        """ Motor de leitura blindado contra texto esmagado e sem quebras de linha """
        # 1. PARSER ROBUSTO (Corta o texto onde encontra as chaves, mesmo sem Enters)
        padrao_chaves = r"(?i)(TAREFA:|PROJETO:|RESPONSÁVEL:|REQUERENTE:|LINK FICHEIROS:|CRITÉRIOS DE ACEITAÇÃO:|PRAZO DE ENTREGA:|OBSERVAÇÕES:|LISTA DE PEÇAS:)"
        partes_texto = re.split(padrao_chaves, texto)
        
        dados = {}
        chave_atual = None
        
        for parte in partes_texto:
            parte_limpa = parte.strip()
            if not parte_limpa: continue
            
            # Se for uma chave reconhecida (ex: "LISTA DE PEÇAS:")
            if re.match(padrao_chaves, parte_limpa):
                chave_atual = parte_limpa.upper().replace(':', '')
                dados[chave_atual] = ""
            elif chave_atual:
                dados[chave_atual] += parte_limpa + " "

        # --- 1. REQUERENTE (Mantém-se Manual) ---
        self.cmb_req.set("")

        # --- 2. LINK E INFERÊNCIA DO PART NUMBER ---
        link = dados.get("LINK FICHEIROS", "").strip()
        pn_inferido = ""
        if link: 
            self.ent_link.delete(0, 'end')
            self.ent_link.insert(0, link)
            pn_inferido = link.replace('/', '\\').split('\\')[-1]

        # --- 3. PROJETO (Tenta adivinhar cruzando as palavras do link) ---
        projeto_extraido = dados.get("PROJETO", "").strip()
        projeto_encontrado = False
        
        if projeto_extraido:
            for p_fmt in self.lista_projetos_fmt:
                if projeto_extraido.lower() in p_fmt.lower():
                    self.cmb_proj.set(p_fmt)
                    projeto_encontrado = True
                    break
                    
        if not projeto_encontrado and link:
            for p_fmt in self.lista_projetos_fmt:
                if p_fmt == "Sem projetos registados": continue
                nome_proj_limpo = p_fmt.split(" - ")[-1]
                palavras_chave = [p.lower() for p in nome_proj_limpo.split() if len(p) > 3]
                for palavra in palavras_chave:
                    if palavra in link.lower():
                        self.cmb_proj.set(p_fmt)
                        projeto_encontrado = True
                        break
                if projeto_encontrado: break

        # --- 4. PRAZO DE ENTREGA ---
        prazo = dados.get("PRAZO DE ENTREGA", "").strip()
        if prazo:
            try:
                data_obj = datetime.strptime(prazo, "%d/%m/%Y")
                self.ent_data.delete(0, 'end')
                self.ent_data.insert(0, data_obj.strftime("%Y-%m-%d"))
            except ValueError:
                self.ent_data.delete(0, 'end')
                self.ent_data.insert(0, prazo)

        # --- 5 & 6. OBSERVAÇÕES E TECNOLOGIA ---
        obs_brutas = dados.get("OBSERVAÇÕES", "").strip()
        crit = dados.get("CRITÉRIOS DE ACEITAÇÃO", "").strip()
        
        obs_upper = obs_brutas.upper()
        if "SLS" in obs_upper: self.cmb_tech.set("SLS")
        elif "FDM" in obs_upper: self.cmb_tech.set("FDM")
        elif "SLA" in obs_upper: self.cmb_tech.set("SLA")

        # Limpar o "lixo" das observações
        obs_brutas = obs_brutas.replace("Email:", "").strip()
        partes_obs = [p.strip() for p in obs_brutas.replace('\n', ';').split(';') if p.strip()]
        obs_restantes = []
        material_inferido = ""
        
        for parte in partes_obs:
            parte_lower = parte.lower()
            if parte_lower.startswith("tecnologia"):
                continue 
            elif parte_lower.startswith("material"):
                if ":" in parte: material_inferido = parte.split(":", 1)[1].strip()
                continue 
            else:
                obs_restantes.append(parte)

        obs_final = ""
        if crit: obs_final += f"Critérios de Aceitação: {crit}\n"
        if obs_restantes: obs_final += "; ".join(obs_restantes)
            
        if obs_final:
            self.txt_obs.delete("1.0", 'end')
            self.txt_obs.insert("1.0", obs_final.strip())

        # --- 7. PROCESSAR LISTA DE PEÇAS (Algoritmo Limpo) ---
        texto_pecas = dados.get("LISTA DE PEÇAS", "").strip()
        
        if texto_pecas:
            # Apaga as linhas vazias que o sistema cria por defeito
            for linha in self.linhas_pecas:
                linha["frame"].destroy()
            self.linhas_pecas = []
            
            # Corta tudo pelos ";" (ex: AQF-001 | PETG Preto | 2 AQF-002 | PETG Preto | 4 AQF-003...)
            segmentos = [s.strip() for s in texto_pecas.split(';') if s.strip()]
            
            pn_atual = segmentos[0] if len(segmentos) > 0 else "S/N"
            idx = 1
            
            while idx < len(segmentos):
                mat_atual = segmentos[idx]
                qtd_raw = segmentos[idx+1] if (idx + 1) < len(segmentos) else "1"
                
                # Procura números no início do 3º segmento (ex: "2 AQF-002" -> Qtd: 2, Próx PN: "AQF-002")
                match_qtd = re.match(r'^(\d+)\s*(.*)$', qtd_raw)
                if match_qtd:
                    qtd_atual = match_qtd.group(1)
                    pn_proximo = match_qtd.group(2).strip()
                else:
                    qtd_atual = "1"
                    pn_proximo = qtd_raw.strip()

                # Adiciona a peça à tabela UI
                self.adicionar_linha_peca()
                l_atual = self.linhas_pecas[-1]
                
                l_atual["pn"].delete(0, 'end')
                l_atual["pn"].insert(0, pn_atual)
                
                l_atual["qtd"].delete(0, 'end')
                l_atual["qtd"].insert(0, qtd_atual)
                
                # Tenta emparelhar o material
                match_mat = False
                for m_fmt in self.lista_materiais_fmt:
                    if mat_atual.lower() in m_fmt.lower():
                        l_atual["mat"].set(m_fmt)
                        match_mat = True
                        break
                if not match_mat:
                    l_atual["mat"].set(mat_atual)

                # Prepara a próxima volta do ciclo
                pn_atual = pn_proximo
                idx += 2
                
                # Segurança: se falhou a leitura do próximo PN, tenta resgatar do segmento seguinte
                if not pn_atual and idx < len(segmentos):
                    pn_atual = segmentos[idx]
                    idx += 1

        # --- 8. FALLBACK (Se não tiver "LISTA DE PEÇAS", tenta usar PN único) ---
        elif material_inferido or pn_inferido:
            if not self.linhas_pecas:
                self.adicionar_linha_peca()
            
            linha = self.linhas_pecas[0]
            if pn_inferido:
                linha["pn"].delete(0, 'end')
                linha["pn"].insert(0, pn_inferido)
                
            linha["qtd"].delete(0, 'end')
            linha["qtd"].insert(0, "1")

            if material_inferido:
                match_mat = False
                for m_fmt in self.lista_materiais_fmt:
                    if material_inferido.lower() in m_fmt.lower():
                        linha["mat"].set(m_fmt)
                        match_mat = True
                        break
                if not match_mat:
                    linha["mat"].set(material_inferido)