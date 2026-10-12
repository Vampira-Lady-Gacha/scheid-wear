# SCHEID · loja online

Loja da SCHEID | STREETWEAR: vitrine do drop atual, sacola, frete, cupom, pagamento por Pix com QR Code e painel para a equipe cuidar das peças e dos pedidos.

Python 3.12 + FastAPI + SQLite (SQLAlchemy 2), páginas renderizadas no servidor com Jinja2, gerenciado com [uv](https://docs.astral.sh/uv/).

## Rodar

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8050
```

Abra http://127.0.0.1:8050. Na primeira vez o banco é criado em `dados/` com as 5 camisetas do DROP 001, e o acesso ao painel fica salvo em `dados/acesso-painel.txt` (troque a senha em `/admin/conta`).

Testes: `uv run pytest`

## O que a loja faz

**Cliente**
- Página inicial com o drop atual: peça destaque com escolha de tamanho e "Adicionar à sacola" na própria tag.
- Catálogo com filtro por categoria, tamanho, busca e ordem.
- Página da peça: galeria, cor, tamanho, quantidade, tabela de medidas, composição e símbolos de lavagem.
- Sacola: cupom, CEP que preenche o endereço sozinho (ViaCEP), frete fixo e frete grátis acima de um valor.
- Pedido: QR Code e Pix copia e cola com o valor exato (sem gateway, sem taxa), ou "Combinar no WhatsApp". Link para acompanhar situação e rastreio.

**Painel (`/admin`)**
- Visão geral: pedidos aguardando pagamento, pagos a enviar, vendido no mês, estoque baixo.
- Peças: criar, editar, duplicar, tirar da loja, apagar; fotos (a primeira é a capa); grade cor × tamanho com estoque; medidas e cuidados.
- Pedidos: marcar pago, enviado, entregue ou cancelado (cancelar devolve ao estoque); código de rastreio; botão para falar com o cliente no WhatsApp.
- Cupons: porcentagem ou valor fixo, compra mínima, limite de usos e validade.
- Loja: drop atual, WhatsApp, Instagram, chave Pix, frete e textos de ajuda.

## Antes de divulgar

1. Em **Loja**: WhatsApp real, chave Pix, nome e cidade do recebedor, valores de frete.
2. Em **Peças**: preço e estoque reais de cada camiseta (hoje R$ 149,90 e estoque de exemplo), tabela de medidas e cuidados.
3. Em produção: defina `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_SENHA`, `COOKIE_SEGURO=1`, `URL_PUBLICA` e, se quiser, `LOJA_DADOS` apontando para um disco persistente.

## Fotos

As fotos do DROP 001 saem das artes da marca em `fotos-originais/`, recortadas por `uv run python scripts/recortar_fotos.py` para `static/img/drop001/`. Fotos novas entram pelo painel.
