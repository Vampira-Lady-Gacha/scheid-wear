"""Templates e utilidades compartilhadas entre a loja e o painel."""

import secrets
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import config
from app.models import PAGAMENTOS, STATUS_PEDIDO, UFS
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


def render(request: Request, sessao: Session, nome: str, contexto: dict[str, Any] | None = None, status: int = 200):
    dados = {
        "request": request,
        "loja": ler_config(sessao),
        "csrf": token_csrf(request),
        "url_publica": config.URL_PUBLICA or str(request.base_url).rstrip("/"),
        "aviso": request.session.pop("aviso", None),
    }
    dados.update(contexto or {})
    return templates.TemplateResponse(request, nome, dados, status_code=status)


def avisar(request: Request, texto: str) -> None:
    request.session["aviso"] = texto
