"""Templates e utilidades compartilhadas entre a loja e o painel."""

import secrets
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import config
from app.models import PAGAMENTOS, STATUS_PEDIDO, UFS, Peca
from app.servicos import CUIDADOS, formatar_telefone, link_whatsapp, ler_config, reais

templates = Jinja2Templates(directory=str(config.RAIZ / "app" / "templates"))
templates.env.filters["reais"] = reais
templates.env.filters["telefone"] = formatar_telefone
templates.env.globals.update(
    link_whatsapp=link_whatsapp,
    STATUS_PEDIDO=STATUS_PEDIDO,
    PAGAMENTOS=PAGAMENTOS,
    UFS=UFS,
    CUIDADOS=CUIDADOS,
    VERSAO_ESTATICOS="1",
)


def token_csrf(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(24)
        request.session["csrf"] = token
    return token


def dados_estaticos(sessao: Session) -> dict[str, Any]:
    """Peças e variantes embutidas na página: na versão estática a sacola calcula tudo no navegador."""
    variantes = {}
    pecas = sessao.scalars(select(Peca).where(Peca.ativa.is_(True)).options(selectinload(Peca.variantes), selectinload(Peca.fotos)))
    for p in pecas:
        for v in p.variantes:
            variantes[v.id] = {
                "peca": p.nome, "numero": p.numero_fmt, "slug": p.slug, "cor": v.cor, "cor_hex": v.cor_hex,
                "tamanho": v.tamanho, "estoque": v.estoque, "preco": p.preco,
                "foto": f"{config.BASE}/media/{p.foto_capa.arquivo}" if p.foto_capa else None,
            }
    return {"variantes": variantes}


def render(request: Request, sessao: Session, nome: str, contexto: dict[str, Any] | None = None, status: int = 200):
    dados = {
        "request": request,
        "loja": ler_config(sessao),
        "csrf": token_csrf(request),
        "url_publica": config.URL_PUBLICA or str(request.base_url).rstrip("/"),
        "aviso": request.session.pop("aviso", None),
        "estatico": config.ESTATICO,
        "base": config.BASE,
    }
    if config.ESTATICO:
        dados["dados_estaticos"] = dados_estaticos(sessao)
    dados.update(contexto or {})
    return templates.TemplateResponse(request, nome, dados, status_code=status)


def avisar(request: Request, texto: str) -> None:
    request.session["aviso"] = texto
