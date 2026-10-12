# Design · SCHEID — Sistema de Etiquetas

A loja é o kit de etiquetas de uma peça SCHEID: tag de papel-cartão com ilhós, etiqueta tecida preta, etiqueta de lavagem em cetim e etiqueta de envio. Fonte dos tokens: `static/css/loja.css` (`:root`).

## Cor

Estratégia contida: papel e tinta, um único acento reservado.

| Token | Valor | Uso |
| --- | --- | --- |
| `--cartao` | `#f1f0ec` | Chão da página (papel-cartão) |
| `--cartao-claro` | `#fbfaf7` | Tags, etiquetas, campos |
| `--cartao-escuro` | `#e3e1db` | Dobra costurada, hover |
| `--tecido` | `#0c0c0d` | Etiqueta tecida, texto, botões, estado ativo |
| `--fio` / `--fio-2` | `#f1f0ec` / `#b9b8b2` | Texto sobre a etiqueta tecida |
| `--tinta-2` | `#4d4c48` | Texto secundário (AA sobre o papel) |
| `--cetim` | `#8a8a86` | Pesponto, tamanho esgotado (decorativo) |
| `--quente` | `#ff5b1a` | Só o que está quente: drop à venda, contador da sacola, últimas unidades, Pix pendente, pedido aguardando pagamento |
| fundo de foto | `#0b0b0c` | Quadro das fotos (o preto das artes da marca) |

Regras: uma etiqueta tecida (placa invertida) por tela. Estado ativo = inversão sólida preta, sem cinzas. Laranja nunca em texto pequeno sobre papel.

## Tipo

- Display: **Anybody** (variável), `font-stretch` 118–150%, peso 850–900, caixa alta. Título do drop até 6rem.
- Rótulos impressos: **Barlow Semi Condensed** 600–700, caixa alta, `letter-spacing` 0.08–0.1em, mínimo 11px.
- Texto: **Barlow** 400–600, 17px / 1.55.
- Fontes servidas pela loja (`static/fonts/`, `static/css/fontes.css`).

## Componentes

- **Tag** (`.tag`): papel claro, cantos de cima chanfrados (`--chanfro`), ilhós com aro metálico, sombra suave. `.tag-grande` para a vitrine e a página da peça.
- **Trilho**: tags penduradas por fio numa barra de arara; alturas de queda alternadas (30/52/40px).
- **Tag pendurada**: barbante do topo até o ilhós; balança ao adicionar à sacola (`balanca`, 1.15s) e assenta ao carregar (`pendura`).
- **Etiqueta tecida** (`.etiqueta-tecida`): trama fina, ourela clara em cima e embaixo, pesponto tracejado nas pontas.
- **Etiqueta de lavagem** (`.lavagem`, `.instrucoes`): cetim com brilho diagonal e dobra costurada no alto; símbolos ISO 3758 desenhados em `_icones.html`.
- **Etiqueta de envio** (`.envio-etiqueta`): borda de 2px, cabeçalho remetente/destinatário, blocos separados por tracejado.
- **Abas de tamanho**: quadrados de 54×48px; escolhido = preto; esgotado = risco diagonal.
- **Placa de foto**: quadrada, `object-fit: contain`, a peça nunca é cortada.
- Botão: preto, rótulo em caixa alta, 50px; `.botao-linha` inverte no hover.

## Movimento

Um único gesto autoral: a tag balança no barbante. `prefers-reduced-motion` desliga tudo.

## Painel

Mesmo papel e tinta, sem encenação (`static/css/admin.css`): navegação ativa por inversão, blocos com fio de 1px, selos de situação; laranja só em "aguardando pagamento".
