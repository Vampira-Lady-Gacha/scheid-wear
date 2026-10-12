"""Páginas públicas da loja e a API da sacola."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import obter_sessao
from app.models import Categoria, Pedido, Peca, Variante
from app.servicos import (
    DadosEntrega,
    ErroPedido,
    cotar,
    criar_pedido,
    ler_config,
    link_whatsapp,
    mensagem_whatsapp,
    pix_do_pedido,
    reais,
)
from app.web import render

roteador = APIRouter()

ORDENS = {
    "drop": (Peca.destaque.desc(), Peca.ordem, Peca.numero),
    "novidades": (Peca.criado_em.desc(), Peca.id.desc()),
    "menor-preco": (Peca.preco.asc(),),
    "maior-preco": (Peca.preco.desc(),),
}


def consulta_pecas():
    return (
        select(Peca)
        .where(Peca.ativa.is_(True))
        .options(selectinload(Peca.fotos), selectinload(Peca.variantes), selectinload(Peca.categoria))
    )


def categorias_com_pecas(sessao: Session) -> list[Categoria]:
    return list(
        sessao.scalars(
            select(Categoria)
            .where(Categoria.ativa.is_(True), Categoria.pecas.any(Peca.ativa.is_(True)))
            .order_by(Categoria.ordem, Categoria.nome)
        )
    )


@roteador.get("/")
def inicio(request: Request, sessao: Session = Depends(obter_sessao)):
    loja = ler_config(sessao)
    pecas = list(sessao.scalars(consulta_pecas().order_by(*ORDENS["drop"])))
    do_drop = [p for p in pecas if p.drop == loja["drop_codigo"]] or pecas
    destaque = next((p for p in do_drop if p.destaque and not p.esgotada), None) or (do_drop[0] if do_drop else None)
    resto = [p for p in do_drop if p is not destaque]
    outras = [p for p in pecas if p not in do_drop]
    return render(
        request,
        sessao,
        "loja/inicio.html",
        {"destaque": destaque, "drop": resto, "outras": outras, "total_drop": len(do_drop)},
    )


@roteador.get("/catalogo")
def catalogo(
    request: Request,
    categoria: str = "",
    tamanho: str = "",
    q: str = "",
    ordem: str = "drop",
    sessao: Session = Depends(obter_sessao),
):
    consulta = consulta_pecas()
    cat_atual = None
    if categoria:
        cat_atual = sessao.scalar(select(Categoria).where(Categoria.slug == categoria))
        if cat_atual is None:
            raise HTTPException(404)
        consulta = consulta.where(Peca.categoria_id == cat_atual.id)
    if tamanho:
        consulta = consulta.where(Peca.variantes.any((Variante.tamanho == tamanho) & (Variante.estoque > 0)))
    if q.strip():
        termo = f"%{q.strip()}%"
        consulta = consulta.where(
            or_(Peca.nome.ilike(termo), Peca.material.ilike(termo), Peca.descricao.ilike(termo), Peca.drop.ilike(termo))
        )
    consulta = consulta.order_by(*ORDENS.get(ordem, ORDENS["drop"]))
    pecas = list(sessao.scalars(consulta))
    tamanhos = list(
        dict.fromkeys(
            t
            for p in sessao.scalars(consulta_pecas())
            for t in p.tamanhos
        )
    )
    return render(
        request,
        sessao,
        "loja/catalogo.html",
        {
            "pecas": pecas,
            "categorias": categorias_com_pecas(sessao),
            "cat_atual": cat_atual,
            "tamanhos": tamanhos,
            "filtro": {"categoria": categoria, "tamanho": tamanho, "q": q, "ordem": ordem},
        },
    )


@roteador.get("/peca/{slug}")
def peca(slug: str, request: Request, sessao: Session = Depends(obter_sessao)):
    item = sessao.scalar(consulta_pecas().where(Peca.slug == slug))
    if item is None:
        raise HTTPException(404)
    outras = list(
        sessao.scalars(consulta_pecas().where(Peca.id != item.id).order_by(*ORDENS["drop"]).limit(3))
    )
    return render(request, sessao, "loja/peca.html", {"peca": item, "outras": outras})


@roteador.get("/sacola")
def sacola(request: Request, sessao: Session = Depends(obter_sessao)):
    return render(request, sessao, "loja/sacola.html")


@roteador.get("/pedido/{codigo}")
def pedido(codigo: str, request: Request, t: str = "", sessao: Session = Depends(obter_sessao)):
    item = sessao.scalar(select(Pedido).where(Pedido.codigo == codigo).options(selectinload(Pedido.itens)))
    if item is None or not t or item.token != t:
        raise HTTPException(404)
    loja = ler_config(sessao)
    return render(
        request,
        sessao,
        "loja/pedido.html",
        {
            "pedido": item,
            "pix": pix_do_pedido(item, loja) if item.status == "aguardando" else None,
            "url_whatsapp": link_whatsapp(loja["whatsapp"], mensagem_whatsapp(item, loja)),
        },
    )


@roteador.get("/ajuda")
def ajuda(request: Request, sessao: Session = Depends(obter_sessao)):
    return render(request, sessao, "loja/ajuda.html")


# ---------------------------------------------------------------- API da sacola


class ItemEntrada(BaseModel):
    variante_id: int
    quantidade: int = Field(ge=1, le=99)


class CotacaoEntrada(BaseModel):
    itens: list[ItemEntrada] = Field(max_length=100)
    cupom: str = Field(default="", max_length=30)


class PedidoEntrada(CotacaoEntrada):
    nome: str = Field(max_length=120)
    email: str = Field(default="", max_length=160)
    whatsapp: str = Field(max_length=30)
    cep: str = Field(max_length=12)
    rua: str = Field(max_length=160)
    numero: str = Field(max_length=20)
    complemento: str = Field(default="", max_length=80)
    bairro: str = Field(max_length=80)
    cidade: str = Field(max_length=80)
    uf: str = Field(max_length=2)
    observacao: str = Field(default="", max_length=1000)
    pagamento: str = "pix"


@roteador.post("/api/cotacao")
def api_cotacao(entrada: CotacaoEntrada, sessao: Session = Depends(obter_sessao)):
    loja = ler_config(sessao)
    c = cotar(sessao, [(i.variante_id, i.quantidade) for i in entrada.itens], loja, entrada.cupom)
    return {
        "linhas": [
            {
                "variante_id": l.variante.id,
                "peca": l.variante.peca.nome,
                "numero": l.variante.peca.numero_fmt,
                "slug": l.variante.peca.slug,
                "foto": f"/media/{l.variante.peca.foto_capa.arquivo}" if l.variante.peca.foto_capa else None,
                "cor": l.variante.cor,
                "cor_hex": l.variante.cor_hex,
                "tamanho": l.variante.tamanho,
                "quantidade": l.quantidade,
                "disponivel": l.variante.estoque,
                "preco_fmt": reais(l.preco_unitario),
                "subtotal_fmt": reais(l.subtotal),
            }
            for l in c.linhas
        ],
        "removidos": c.removidos,
        "quantidade": c.quantidade,
        "subtotal_fmt": reais(c.subtotal),
        "desconto": c.desconto,
        "desconto_fmt": reais(c.desconto),
        "cupom": c.cupom.codigo if c.cupom else "",
        "erro_cupom": c.erro_cupom,
        "frete": c.frete,
        "frete_fmt": reais(c.frete) if c.frete else "Grátis",
        "falta_frete_gratis_fmt": reais(c.falta_frete_gratis) if c.falta_frete_gratis else "",
        "total_fmt": reais(c.total),
    }


@roteador.post("/api/pedidos")
def api_criar_pedido(entrada: PedidoEntrada, sessao: Session = Depends(obter_sessao)):
    loja = ler_config(sessao)
    dados = entrada.model_dump(exclude={"itens", "cupom", "pagamento"})
    try:
        novo = criar_pedido(
            sessao,
            [(i.variante_id, i.quantidade) for i in entrada.itens],
            DadosEntrega(**dados),
            loja=loja,
            pagamento=entrada.pagamento,
            cupom=entrada.cupom,
        )
    except ErroPedido as erro:
        sessao.rollback()
        return JSONResponse({"erro": str(erro)}, status_code=422)
    return {
        "codigo": novo.codigo,
        "url": f"/pedido/{novo.codigo}?t={novo.token}",
        "url_whatsapp": link_whatsapp(loja["whatsapp"], mensagem_whatsapp(novo, loja)),
    }


# ---------------------------------------------------------------- SEO


@roteador.get("/robots.txt", response_class=PlainTextResponse)
def robots(request: Request):
    return (
        "User-agent: *\nDisallow: /admin\nDisallow: /api\nDisallow: /pedido\nDisallow: /sacola\n"
        f"Sitemap: {str(request.base_url).rstrip('/')}/sitemap.xml\n"
    )


@roteador.get("/sitemap.xml")
def sitemap(request: Request, sessao: Session = Depends(obter_sessao)):
    base = str(request.base_url).rstrip("/")
    hoje = date.today().isoformat()
    urls = [f"{base}/", f"{base}/catalogo", f"{base}/ajuda"]
    urls += [f"{base}/catalogo?categoria={c.slug}" for c in categorias_com_pecas(sessao)]
    urls += [f"{base}/peca/{p.slug}" for p in sessao.scalars(select(Peca).where(Peca.ativa.is_(True)))]
    corpo = "".join(f"<url><loc>{u.replace('&', '&amp;')}</loc><lastmod>{hoje}</lastmod></url>" for u in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{corpo}</urlset>'
    return Response(xml, media_type="application/xml")
