# Modelo de email para criação automática de pedidos

O botão **"📥 Importar de Email"** (em Gestão de Pedidos → Novo Pedido) lê o texto
colado e tenta preencher o formulário sozinho. Para isso funcionar de forma
fiável, o email tem de seguir esta estrutura — as palavras-chave (antes dos
":") têm de aparecer exatamente como abaixo.

## Modelo

```
TAREFA: <descrição curta do que é pedido>
PROJETO: <número - nome, tem de bater certo com um projeto já registado>
RESPONSÁVEL: <nome de quem acompanha o projeto>
REQUERENTE: <email de quem pede>
LINK FICHEIROS: <caminho de rede ou link para os ficheiros>
PRAZO DE ENTREGA: DD/MM/AAAA
CRITÉRIOS DE ACEITAÇÃO: <tolerâncias, acabamento, etc.>
OBSERVAÇÕES: Tecnologia: FDM|SLA|SLS; Material: <nome do material>; <notas livres>
LISTA DE PEÇAS: <PN1>; <Material1>; <Qtd1> <PN2>; <Material2>; <Qtd2> ...
```

## Exemplo real

```
TAREFA: Fabrico de peças para protótipo
PROJETO: 257147 - PPS AquaFountain
RESPONSÁVEL: Ana Moura
REQUERENTE: joao.silva@ceiia.com
LINK FICHEIROS: \\ceiia.com\PPS\AquaFountain
PRAZO DE ENTREGA: 20/09/2026
CRITÉRIOS DE ACEITAÇÃO: Tolerância dimensional ±0.2mm
OBSERVAÇÕES: Tecnologia: FDM; Material: PETG Preto; Entregar em saco individual por peça.
LISTA DE PEÇAS: AQF-001-Base; PETG Preto; 10 AQF-002-Tampa; PETG Preto; 5
```

## Pontos importantes (e não óbvios)

- **Requerente não é lido do email.** O sistema deixa sempre esse campo vazio
  de propósito — quem cria o pedido no AManager escolhe/confirma manualmente,
  mesmo que a linha `REQUERENTE:` esteja preenchida no email.
- **Tecnologia e Material não são chaves de topo.** Vão *dentro* do bloco
  `OBSERVAÇÕES:`, no formato `Tecnologia: FDM` / `Material: Nome`, separados
  por `;`. Se só quiser garantir a tecnologia sem indicar material, basta que
  a palavra "FDM", "SLA" ou "SLS" apareça em qualquer parte das observações.
- **`LISTA DE PEÇAS` usa `;` como único separador — nunca `|`.** O formato é
  `PN; Material; Quantidade` repetido, onde a quantidade e o PN seguinte
  aparecem juntos no mesmo bloco (ex: `...; 10 AQF-002-Tampa; ...`), sem `;`
  entre eles. Sem peças aqui, o sistema tenta adivinhar uma peça única a
  partir do nome do ficheiro no link.
- **Datas** em `PRAZO DE ENTREGA` devem estar em `DD/MM/AAAA`; formatos
  diferentes ficam guardados tal como escritos, sem conversão.
- **Projeto** só é reconhecido automaticamente se o texto depois de
  `PROJETO:` corresponder (mesmo que parcialmente) a um projeto já existente
  em *Gestão de Pedidos → Gerir Projetos / Materiais*, ou se uma palavra do
  nome do projeto aparecer no link de ficheiros.

Este modelo foi verificado diretamente contra o código do parser
(`gui/dialogs/novo_pedido.py::processar_texto_email`).
