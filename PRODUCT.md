# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python 3.12 + FastAPI + SQLite (SQLAlchemy 2), páginas renderizadas no servidor com Jinja2, gerenciado com uv. Escolhido pelo usuário entre as opções oferecidas (mesma arquitetura da loja Vanuza Andrade). Hospedagem prevista em serviço de container simples (Render/Railway); ainda não decidida.

## Users

- **Cliente:** jovem que chega pelo Instagram (@scheidwear), vê o drop no celular e quer escolher tamanho, ver o preço com frete e pagar na hora, de qualquer lugar do Brasil.
- **Equipe SCHEID (painel):** cadastra e edita peças, fotos, cores, tamanhos e estoque; tira peças do ar; acompanha pedidos, confirma pagamento Pix, informa código de rastreio; cria cupons; ajusta frete e textos da loja. Usa o celular.

## Product Purpose

Loja online própria da SCHEID: apresentar o drop atual e vender sem depender do direct. O cliente monta o carrinho, informa o CEP (endereço preenchido sozinho), vê o frete, aplica cupom e paga por Pix com QR Code e copia-e-cola gerados com o valor exato; pode também chamar no WhatsApp. O pedido fica registrado no painel. Sucesso: pedidos pagos chegando prontos, sem conversa para tirar dúvida de tamanho, preço e frete.

## Positioning

Marca de streetwear com linguagem de esporte e cultura de rua, lançada em drops numerados. Primeiro drop: DROP 001 — AFTER HOURS.

## Operating Context

- Venda só online, envio para todo o Brasil. Sem loja física conhecida.
- Pagamento por Pix estático (chave configurável no painel); a equipe confere o recebimento e marca o pedido como pago. Sem gateway.
- Frete: valor fixo configurável e frete grátis acima de um valor configurável.
- Instagram: @scheidwear (22 seguidores em out/2026, perfil recém-lançado).

## Capabilities and Constraints

- Catálogo com categorias, peças, várias fotos por peça, variações de cor e tamanho com estoque, preço e preço "de" (riscado) opcional.
- Peça pode pertencer a um drop; drop atual configurável no painel.
- Grade padrão de tamanhos: P, M, G, GG (editável por peça).
- Carrinho no navegador; o servidor recalcula preço, frete, cupom e estoque.
- Cupons de desconto (percentual ou valor fixo, ativo/inativo, pedido mínimo).
- Pedido com status: aguardando pagamento, pago, enviado (com rastreio), entregue, cancelado. Cancelar devolve ao estoque.
- Painel com login: visão geral, peças, categorias, pedidos, cupons, configurações, conta.
- Ainda não decidido: número do WhatsApp, chave Pix, valores de frete, domínio, preços, estoque e medidas das peças.

## Brand Commitments

- Nome: SCHEID (perfil "SCHEID | STREETWEAR"). Logo: palavra SCHEID em caixa alta, geométrica e larga, branca sobre preto; abaixo um fio e "STREETWEAR • SPORT • CULTURE". Monograma "SCD" e símbolo da coroa sobre o S (usado em pin de metal). Etiqueta tecida interna SCHEID / VISTA O SEU MOVIMENTO. / tamanho; etiqueta lateral SCD 001. Tags de papel preta (SCHEID) e off-white (VISTA O SEU MOVIMENTO.).
- Linha: "STREETWEAR • SPORT • CULTURE". Bordão: "VISTA O SEU MOVIMENTO."
- Drop atual: "DROP 001 — AFTER HOURS". Chamada do perfil: "Compre o DROP".
- Tom: direto, curto, caixa alta nas chamadas; português do Brasil.

## Evidence on Hand

- Texto do perfil do Instagram.
- Artes do DROP 001 enviadas pela marca, em `fotos-originais/`: grade das 5 camisetas (frente, costas, manga, etiquetas), apresentação da SCHEID BASIC (mockups, fotos "como fica", tags, embalagem) e uma referência de looks. Recortadas em `static/img/drop001/` por `scripts/recortar_fotos.py`.
- DROP 001 = 5 camisetas oversized, 100% algodão, gramatura pesada, unissex: 01 SCHEID BASIC (preto), 02 AFTER HOURS (off-white), 03 SCD SPORT (verde militar), 04 NO RULES (cinza), 05 CULTURE (preto lavado).
- Texto do drop (das artes): "Inspirado na cidade, na noite e na liberdade de ser quem você é. Peças feitas para o seu dia, do seu jeito."
- A referência de looks mostra marcas de terceiros (Calvin Klein, Nike, Vans) e o nome "SCHEIDEGGER": não usar como foto de produto.
- Logos enviados no chat (monograma da coroa, selo circular SCD/SCHEID, escudo com raio), ainda não salvos no projeto.
- NÃO conhecidos: preço, estoque, tabela de medidas e cuidados de lavagem. O catálogo usa R$ 149,90 e estoque de exemplo, marcados para revisão no painel.
- Não há depoimentos, avaliações, números de clientes nem prêmios. Não inventar.

## Product Principles

1. O drop é o evento: a loja abre mostrando o que está à venda agora.
2. Do Instagram ao Pix em poucos toques: tamanho, CEP, pagar.
3. O servidor é a fonte do preço, do frete e do estoque.
4. O painel funciona no celular, com uma mão.
5. Nada de alegação que a marca não confirmou.

## Accessibility & Inclusion

Uso majoritário em celular com dados móveis: páginas leves, fotos otimizadas, contraste AA e alvos de toque de pelo menos 44 px.
