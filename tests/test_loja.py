from datetime import date, timedelta

from sqlalchemy import select

from app.models import Cupom, Pedido, Peca, Variante
from app.servicos import _crc16, payload_pix, salvar_config
from tests.conftest import ENDERECO, csrf_de


def variante(sessao, nome_peca: str, tamanho: str = "M") -> Variante:
    peca = sessao.scalar(select(Peca).where(Peca.nome == nome_peca))
    return next(v for v in peca.variantes if v.tamanho == tamanho)


def pedir(cliente, itens, **extra):
    corpo = {**ENDERECO, "itens": itens, **extra}
    return cliente.post("/api/pedidos", json=corpo)


# ---------------------------------------------------------------- páginas


def test_paginas_publicas_abrem(cliente):
    for url in ["/", "/catalogo", "/catalogo?categoria=camisetas", "/catalogo?tamanho=GG&ordem=menor-preco",
                "/catalogo?q=moletom", "/peca/camiseta-after-hours", "/sacola", "/ajuda",
                "/robots.txt", "/sitemap.xml"]:
        assert cliente.get(url).status_code == 200, url


def test_inicio_mostra_drop_e_destaque(cliente):
    html = cliente.get("/").text
    assert "AFTER HOURS" in html
    assert "Camiseta After Hours" in html
    assert "Adicionar à sacola" in html
    assert "Nº 002" in html


def test_peca_inexistente_da_404(cliente):
    resp = cliente.get("/peca/nao-existe")
    assert resp.status_code == 404
    assert "Essa etiqueta não existe" in resp.text


def test_peca_mostra_material_galeria_e_dados_estruturados(cliente):
    html = cliente.get("/peca/camiseta-scheid-basic").text
    assert "100% algodão, gramatura pesada" in html
    assert "drop001-scheid-basic-como-fica-1.jpg" in html
    assert '"@type": "Product"' in html


# ---------------------------------------------------------------- cotação, frete e cupom


def test_cotacao_calcula_frete_fixo_e_gratis(cliente, sessao):
    camiseta = variante(sessao, "Camiseta After Hours")
    um = cliente.post("/api/cotacao", json={"itens": [{"variante_id": camiseta.id, "quantidade": 1}]}).json()
    assert um["subtotal_fmt"] == "R$ 149,90"
    assert um["frete_fmt"] == "R$ 24,90"
    assert um["total_fmt"] == "R$ 174,80"
    assert um["falta_frete_gratis_fmt"] == "R$ 149,10"

    dois = cliente.post("/api/cotacao", json={"itens": [{"variante_id": camiseta.id, "quantidade": 2}]}).json()
    assert dois["frete_fmt"] == "Grátis"
    assert dois["total_fmt"] == "R$ 299,80"


def test_cupom_percentual_e_invalido(cliente, sessao):
    sessao.add(Cupom(codigo="DROP10", tipo="percentual", valor=10))
    sessao.add(Cupom(codigo="VELHO", tipo="valor", valor=1000, validade=date.today() - timedelta(days=1)))
    sessao.commit()
    camiseta = variante(sessao, "Camiseta After Hours")
    itens = [{"variante_id": camiseta.id, "quantidade": 1}]

    ok = cliente.post("/api/cotacao", json={"itens": itens, "cupom": "drop10"}).json()
    assert ok["cupom"] == "DROP10"
    assert ok["desconto_fmt"] == "R$ 14,99"
    assert ok["total_fmt"] == "R$ 159,81"

    vencido = cliente.post("/api/cotacao", json={"itens": itens, "cupom": "VELHO"}).json()
    assert vencido["erro_cupom"] == "Esse cupom venceu."
    assert vencido["desconto"] == 0

    nenhum = cliente.post("/api/cotacao", json={"itens": itens, "cupom": "NAOEXISTE"}).json()
    assert nenhum["erro_cupom"] == "Cupom não encontrado."


# ---------------------------------------------------------------- pedido


def test_criar_pedido_baixa_estoque_e_mostra_pix(cliente, sessao):
    salvar_config(sessao, {"pix_chave": "pix@scheid.com.br"})
    v = variante(sessao, "Camiseta After Hours", "G")
    antes = v.estoque
    resp = pedir(cliente, [{"variante_id": v.id, "quantidade": 2}])
    assert resp.status_code == 200, resp.text
    dados = resp.json()
    assert dados["codigo"] == "SCD-0001"

    sessao.expire_all()
    assert sessao.get(Variante, v.id).estoque == antes - 2
    pedido = sessao.scalar(select(Pedido))
    assert pedido.total == 29980 and pedido.frete == 0
    assert pedido.cidade == "São Paulo" and pedido.cep == "01310100"

    pagina = cliente.get(dados["url"])
    assert pagina.status_code == 200
    assert "Pix pendente" in pagina.text
    assert "<svg" in pagina.text and "br.gov.bcb.pix" in pagina.text
    assert "5204000053039865406299.80" in pagina.text


def test_pedido_sem_chave_pix_vai_para_whatsapp(cliente, sessao):
    v = variante(sessao, "Camiseta Culture")
    dados = pedir(cliente, [{"variante_id": v.id, "quantidade": 1}]).json()
    pagina = cliente.get(dados["url"]).text
    assert "Enviar pedido no WhatsApp" in pagina
    assert "Pix pendente" not in pagina


def test_pedido_valida_endereco_e_estoque(cliente, sessao):
    v = variante(sessao, "Camiseta After Hours", "GG")
    sem_cep = pedir(cliente, [{"variante_id": v.id, "quantidade": 1}], cep="123")
    assert sem_cep.status_code == 422
    assert "CEP" in sem_cep.json()["erro"]

    so_nome = pedir(cliente, [{"variante_id": v.id, "quantidade": 1}], nome="Maria")
    assert "sobrenome" in so_nome.json()["erro"]

    demais = pedir(cliente, [{"variante_id": v.id, "quantidade": v.estoque + 1}])
    assert demais.status_code == 422
    assert "só temos" in demais.json()["erro"]


def test_link_do_pedido_exige_token(cliente, sessao):
    v = variante(sessao, "Camiseta No Rules")
    dados = pedir(cliente, [{"variante_id": v.id, "quantidade": 1}]).json()
    assert cliente.get(f"/pedido/{dados['codigo']}").status_code == 404
    assert cliente.get(f"/pedido/{dados['codigo']}?t=errado").status_code == 404


def test_cupom_conta_uso_e_respeita_limite(cliente, sessao):
    sessao.add(Cupom(codigo="UMAVEZ", tipo="valor", valor=2000, limite_usos=1))
    sessao.commit()
    v = variante(sessao, "Camiseta No Rules")
    primeiro = pedir(cliente, [{"variante_id": v.id, "quantidade": 1}], cupom="UMAVEZ")
    assert primeiro.status_code == 200
    segundo = pedir(cliente, [{"variante_id": v.id, "quantidade": 1}], cupom="UMAVEZ")
    assert segundo.status_code == 422
    assert "máximo" in segundo.json()["erro"]


# ---------------------------------------------------------------- Pix


def test_crc16_ccitt():
    assert _crc16("123456789") == "29B1"


def test_payload_pix_tem_campos_e_crc_valido():
    codigo = payload_pix("pix@scheid.com.br", 17480, "Scheid Streetwear Ltda", "São Paulo", "SCD-0007")
    assert codigo.startswith("000201")
    assert "0014br.gov.bcb.pix0117pix@scheid.com.br" in codigo
    assert "540517480"[0:4] == "5405" and "5406174.80" in codigo
    assert "5922SCHEID STREETWEAR LTDA" in codigo
    assert "6009SAO PAULO" in codigo
    assert "62110507SCD0007" in codigo
    assert codigo[-8:-4] == "6304"
    assert codigo[-4:] == _crc16(codigo[:-4])


# ---------------------------------------------------------------- painel


def test_painel_exige_login(cliente):
    resp = cliente.get("/admin", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/entrar"


def test_painel_abre_todas_as_telas(admin, sessao):
    peca = sessao.scalar(select(Peca))
    for url in ["/admin", "/admin/pedidos", "/admin/pecas", f"/admin/pecas/{peca.id}", "/admin/pecas/nova",
                "/admin/categorias", "/admin/cupons", "/admin/configuracoes", "/admin/conta"]:
        assert admin.get(url).status_code == 200, url


def test_criar_peca_pelo_painel(admin, sessao):
    pagina = admin.get("/admin/pecas/nova")
    resp = admin.post(
        "/admin/pecas/nova",
        data={
            "csrf": csrf_de(pagina.text), "nome": "Calça Cargo Noturna", "preco": "259,90", "preco_de": "",
            "drop": "drop 001", "material": "Sarja", "ativa": "on", "cuidados": ["lavar-30", "inventado"],
            "medidas": "Tam | Cintura\nP | 38",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    peca = sessao.scalar(select(Peca).where(Peca.nome == "Calça Cargo Noturna"))
    assert peca.preco == 25990 and peca.drop == "DROP 001" and peca.numero == 6
    assert peca.cuidados == "lavar-30"
    assert peca.tabela_medidas == [["Tam", "Cintura"], ["P", "38"]]
    assert {v.tamanho for v in peca.variantes} == {"P", "M", "G", "GG"}


def test_preco_de_menor_que_preco_e_recusado(admin, sessao):
    peca = sessao.scalar(select(Peca))
    pagina = admin.get(f"/admin/pecas/{peca.id}")
    resp = admin.post(
        f"/admin/pecas/{peca.id}",
        data={"csrf": csrf_de(pagina.text), "nome": peca.nome, "preco": "100,00", "preco_de": "90,00"},
    )
    assert resp.status_code == 422
    assert "preço “de”" in resp.text


def test_cancelar_devolve_estoque_e_rastreio_marca_enviado(admin, sessao):
    v = variante(sessao, "Camiseta SCD Sport")
    antes = v.estoque
    pedir(admin, [{"variante_id": v.id, "quantidade": 1}])
    pedido = sessao.scalar(select(Pedido))
    pagina = admin.get(f"/admin/pedidos/{pedido.id}")
    csrf = csrf_de(pagina.text)

    admin.post(f"/admin/pedidos/{pedido.id}/status", data={"csrf": csrf, "status": "cancelado"})
    sessao.expire_all()
    assert sessao.get(Variante, v.id).estoque == antes

    admin.post(f"/admin/pedidos/{pedido.id}/status", data={"csrf": csrf, "status": "pago"})
    sessao.expire_all()
    assert sessao.get(Variante, v.id).estoque == antes - 1
    assert sessao.get(Pedido, pedido.id).pago_em is not None

    admin.post(f"/admin/pedidos/{pedido.id}/rastreio", data={"csrf": csrf, "rastreio": "aa123456789br"})
    sessao.expire_all()
    atualizado = sessao.get(Pedido, pedido.id)
    assert atualizado.status == "enviado" and atualizado.rastreio == "AA123456789BR"
    assert "AA123456789BR" in admin.get(f"/pedido/{atualizado.codigo}?t={atualizado.token}").text


def test_criar_cupom_pelo_painel(admin, sessao):
    pagina = admin.get("/admin/cupons")
    csrf = csrf_de(pagina.text)
    ok = admin.post("/admin/cupons", data={"csrf": csrf, "codigo": "after 15", "tipo": "percentual", "valor": "15"},
                    follow_redirects=False)
    assert ok.status_code == 303
    assert sessao.scalar(select(Cupom).where(Cupom.codigo == "AFTER15")).valor == 15
    ruim = admin.post("/admin/cupons", data={"csrf": csrf, "codigo": "X", "tipo": "percentual", "valor": "150"})
    assert ruim.status_code == 422


def test_configuracoes_normalizam_valores(admin, sessao):
    from app.servicos import ler_config

    pagina = admin.get("/admin/configuracoes")
    admin.post("/admin/configuracoes", data={
        "csrf": csrf_de(pagina.text), "whatsapp": "+55 (11) 91234-5678", "instagram": "@scheidwear",
        "frete_fixo": "19.9", "frete_gratis_acima": "", "pix_chave": "123.456.789-09",
    })
    loja = ler_config(sessao)
    assert loja["whatsapp"] == "5511912345678"
    assert loja["instagram"] == "scheidwear"
    assert loja["frete_fixo"] == "19,90"
    assert loja["frete_gratis_acima"] == ""
    assert loja["pix_chave"] == "12345678909"


def test_post_sem_csrf_e_recusado(admin, sessao):
    peca = sessao.scalar(select(Peca))
    resp = admin.post(f"/admin/pecas/{peca.id}/apagar", data={"csrf": "falso"})
    assert resp.status_code == 400
    assert sessao.get(Peca, peca.id) is not None
