"""Cria as tabelas, o usuário do painel e o catálogo inicial.

Uso: uv run python -m app.seed            (só cria o que falta)
     uv run python -m app.seed --senha    (gera uma nova senha para o painel)
"""

import os
import secrets
import shutil
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.db import Base, SessaoLocal, engine
from app.models import Categoria, Foto, Peca, Usuario, Variante
from app.servicos import gerar_hash, slugificar

PASTA_FOTOS = config.RAIZ / "static" / "img" / "drop001"

MATERIAL = "100% algodão, gramatura pesada. Modelagem oversized, unissex."
GRADE_EXEMPLO = {"P": 6, "M": 10, "G": 10, "GG": 6}


def fotos(prefixo: str, primeiras: list[str]) -> list[str]:
    resto = [f"{prefixo}-{v}.jpg" for v in ("frente", "costas", "manga", "etiqueta-interna", "etiqueta-lateral")]
    return primeiras + [f for f in resto if f not in primeiras]


# DROP 001 — AFTER HOURS, como nas artes enviadas pela SCHEID (fotos-originais/).
# Nomes, cores, estampas e material vêm das artes. Preço e estoque NÃO: são exemplo, revise no painel.
CATALOGO_INICIAL = [
    {
        "nome": "Camiseta Scheid Basic",
        "descricao": "Minimalista e clean. SCHEID pequeno no peito; nas costas, SCHEID com STREETWEAR • SPORT • CULTURE, 001 e VISTA O SEU MOVIMENTO. SCD na manga.",
        "cor": ("Preto", "#111112"),
        "fotos": fotos("scheid-basic", [
            "scheid-basic-mockup-frente.jpg", "scheid-basic-mockup-costas.jpg",
            "scheid-basic-como-fica-1.jpg", "scheid-basic-como-fica-2.jpg", "scheid-basic-como-fica-3.jpg",
        ]),
    },
    {
        "nome": "Camiseta After Hours",
        "descricao": "Arte urbana exclusiva. AFTER HOURS em traço de pixo nas costas com NO RULES. JUST YOUR STYLE.; SCD no peito e etiqueta SCHEID na manga.",
        "cor": ("Off-white", "#e9e5da"),
        "fotos": fotos("after-hours", ["after-hours-costas.jpg", "after-hours-frente.jpg"]),
        "destaque": True,
    },
    {
        "nome": "Camiseta SCD Sport",
        "descricao": "Inspirada no esporte e na rua. SCHEID 001 em letra universitária nas costas, SCHEID no peito e 001 na manga.",
        "cor": ("Verde militar", "#3c4630"),
        "fotos": fotos("scd-sport", ["scd-sport-costas.jpg", "scd-sport-frente.jpg"]),
    },
    {
        "nome": "Camiseta No Rules",
        "descricao": "Atitude, liberdade e originalidade. NO RULES. no peito e NO RULES. JUST YOUR STYLE. nas costas, em letra cursiva.",
        "cor": ("Cinza", "#5d5d5c"),
        "fotos": fotos("no-rules", ["no-rules-costas.jpg", "no-rules-frente.jpg"]),
    },
    {
        "nome": "Camiseta Culture",
        "descricao": "Vintage feel premium. Malha preto lavado, SCHEID CULTURE no peito e a cidade à noite nas costas.",
        "cor": ("Preto lavado", "#2a2a2a"),
        "fotos": fotos("culture", ["culture-costas.jpg", "culture-frente.jpg"]),
    },
]

CATEGORIAS = ["Camisetas"]


def criar_tabelas() -> None:
    Base.metadata.create_all(engine)


def garantir_admin(sessao: Session, nova_senha: bool = False) -> str | None:
    """Cria o usuário do painel. Devolve onde a senha foi salva quando ela foi gerada agora."""
    email = os.environ.get("ADMIN_EMAIL", "admin@scheid.com.br").strip().lower()
    usuario = sessao.scalar(select(Usuario).where(Usuario.email == email))
    if usuario and not nova_senha:
        return None
    senha = os.environ.get("ADMIN_SENHA") or secrets.token_urlsafe(9)
    if usuario is None:
        usuario = Usuario(email=email, nome="SCHEID", senha_hash=gerar_hash(senha))
        sessao.add(usuario)
    else:
        usuario.senha_hash = gerar_hash(senha)
    sessao.commit()
    if os.environ.get("ADMIN_SENHA"):
        return None
    arquivo = config.PASTA_DADOS / "acesso-painel.txt"
    arquivo.write_text(f"E-mail: {email}\nSenha: {senha}\nTroque a senha em /admin/conta.\n", encoding="utf-8")
    return str(arquivo)


def popular_catalogo(sessao: Session) -> bool:
    if sessao.scalar(select(Peca.id).limit(1)) is not None:
        return False
    config.PASTA_UPLOADS.mkdir(parents=True, exist_ok=True)
    categorias: dict[str, Categoria] = {}
    for ordem, nome in enumerate(CATEGORIAS):
        categorias[nome] = Categoria(nome=nome, slug=slugificar(nome), ordem=ordem)
        sessao.add(categorias[nome])

    for ordem, dados in enumerate(CATALOGO_INICIAL):
        peca = Peca(
            numero=ordem + 1,
            nome=dados["nome"],
            slug=slugificar(dados["nome"]),
            drop="DROP 001",
            categoria=categorias["Camisetas"],
            material=MATERIAL,
            descricao=dados["descricao"],
            preco=14990,
            destaque=dados.get("destaque", False),
            ordem=ordem,
        )
        for posicao, arquivo in enumerate(dados["fotos"]):
            destino = f"drop001-{arquivo}"
            shutil.copyfile(PASTA_FOTOS / arquivo, config.PASTA_UPLOADS / destino)
            peca.fotos.append(Foto(arquivo=destino, ordem=posicao))
        cor, hexa = dados["cor"]
        for tamanho, qtd in GRADE_EXEMPLO.items():
            peca.variantes.append(Variante(cor=cor, cor_hex=hexa, tamanho=tamanho, estoque=qtd))
        sessao.add(peca)
    sessao.commit()
    return True


def preparar(nova_senha: bool = False, catalogo: bool = True) -> str | None:
    criar_tabelas()
    with SessaoLocal() as sessao:
        arquivo = garantir_admin(sessao, nova_senha)
        if catalogo:
            popular_catalogo(sessao)
    return arquivo


if __name__ == "__main__":
    gerado = preparar(nova_senha="--senha" in sys.argv)
    if gerado:
        print(f"Acesso ao painel salvo em {gerado}")
    print("Banco pronto.")
