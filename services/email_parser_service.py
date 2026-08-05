from datetime import datetime
import re
import os


def processar_texto_email(self, texto):
        """ Motor de leitura do texto baseado em Regex, à prova de texto colado e sem quebras de linha """
        # 1. PARSER ROBUSTO (Usa Regex para cortar o texto onde estiverem as chaves)
        chaves = ["TAREFA:", "PROJETO:", "RESPONSÁVEL:", "REQUERENTE:", "LINK FICHEIROS:", "CRITÉRIOS DE ACEITAÇÃO:", "PRAZO DE ENTREGA:", "OBSERVAÇÕES:", "LISTA DE PEÇAS:"]
        padrao = "(?i)(" + "|".join(chaves) + ")"
        
        partes_texto = re.split(padrao, texto)
        
        dados = {}
        chave_atual = None
        
        for parte in partes_texto:
            parte_upper = parte.strip().upper()
            if parte_upper in chaves:
                chave_atual = parte_upper.replace(':', '')
                dados[chave_atual] = ""
            elif chave_atual:
                dados[chave_atual] += parte.strip() + " "

        # --- 1. REQUERENTE ---
        # Como definido, mantém-se manual nesta fase. O sistema não tenta preencher automaticamente.
        self.cmb_req.set("")

        # --- 2. LINK E INFERÊNCIA DO PART NUMBER ---
        link = dados.get("LINK FICHEIROS", "").strip()
        pn_inferido = ""
        if link: 
            self.ent_link.delete(0, 'end')
            self.ent_link.insert(0, link)
            partes_link = link.replace('/', '\\').split('\\')
            if partes_link:
                pn_inferido = partes_link[-1]

        # --- 3. PROJETO (Heurística Aprimorada) ---
        projeto_extraido = dados.get("PROJETO", "").strip()
        projeto_encontrado = False
        
        if projeto_extraido:
            for p_fmt in self.lista_projetos_fmt:
                if projeto_extraido.lower() in p_fmt.lower():
                    self.cmb_proj.set(p_fmt)
                    projeto_encontrado = True
                    break
                    
        # Se não vier escrito explicitamente, tenta adivinhar procurando palavras-chave do projeto no link
        if not projeto_encontrado and link:
            for p_fmt in self.lista_projetos_fmt:
                if p_fmt == "Sem projetos registados": continue
                nome_proj_limpo = p_fmt.split(" - ")[-1]
                # Usa apenas palavras com +3 letras para procurar (ex: ignora "PPS", "do", etc)
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

        # Limpeza cirúrgica das observações
        obs_brutas = obs_brutas.replace("Email:", "").strip()
        partes_obs = [p.strip() for p in obs_brutas.replace('\n', ';').split(';') if p.strip()]
        obs_restantes = []
        material_inferido = ""
        
        for parte in partes_obs:
            parte_lower = parte.lower()
            if parte_lower.startswith("tecnologia:") or parte_lower.startswith("tecnologia "):
                continue 
            elif parte_lower.startswith("material:") or parte_lower.startswith("material "):
                if ":" in parte:
                    material_inferido = parte.split(":", 1)[1].strip()
                continue 
            else:
                obs_restantes.append(parte)

        obs_final = ""
        if crit: 
            obs_final += f"Critérios de Aceitação: {crit}\n"
        if obs_restantes:
            obs_final += "; ".join(obs_restantes)
            
        if obs_final:
            self.txt_obs.delete("1.0", 'end')
            self.txt_obs.insert("1.0", obs_final.strip())

        # --- 7. PROCESSAR LISTA DE PEÇAS (À Prova de Copy-Paste "Esmagado") ---
        texto_pecas = dados.get("LISTA DE PEÇAS", "").strip()
        
        if texto_pecas:
            for linha in self.linhas_pecas:
                linha["frame"].destroy()
            self.linhas_pecas = []
            
            # Divide tudo por ; e processa os blocos, resolvendo as uniões "2 AQF-002" causadas pela falta de Enters
            partes_raw = [p.strip() for p in texto_pecas.split(';') if p.strip()]
            
            if len(partes_raw) >= 3:
                buffer_pn = partes_raw[0]
                for i in range(1, len(partes_raw), 2):
                    mat_lista = partes_raw[i]
                    qtd_lista = "1"
                    
                    if i + 1 < len(partes_raw):
                        # Corta no primeiro espaço para separar a Quantidade do próximo Part Number
                        qtd_e_prox = partes_raw[i+1].split(None, 1)
                        qtd_lista = "".join(filter(str.isdigit, qtd_e_prox[0]))
                        if not qtd_lista: qtd_lista = "1"
                        
                        self.adicionar_linha_peca()
                        l_atual = self.linhas_pecas[-1]
                        l_atual["pn"].delete(0, 'end')
                        l_atual["pn"].insert(0, buffer_pn)
                        l_atual["qtd"].delete(0, 'end')
                        l_atual["qtd"].insert(0, qtd_lista)
                        
                        match_encontrado = False
                        for m_fmt in self.lista_materiais_fmt:
                            if mat_lista.lower() in m_fmt.lower():
                                l_atual["mat"].set(m_fmt)
                                match_encontrado = True
                                break
                        if not match_encontrado:
                            l_atual["mat"].set(mat_lista)

                        # Guarda o próximo Part Number em memória para a próxima volta do ciclo
                        if len(qtd_e_prox) > 1:
                            buffer_pn = qtd_e_prox[1].strip()
                        else:
                            buffer_pn = ""

        # --- 8. FALLBACK (Se só tiver havido uma peça e sem tabela de peças) ---
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
                match_encontrado = False
                for m_fmt in self.lista_materiais_fmt:
                    if material_inferido.lower() in m_fmt.lower():
                        linha["mat"].set(m_fmt)
                        match_encontrado = True
                        break
                if not match_encontrado:
                    linha["mat"].set(material_inferido)