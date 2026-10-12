"""Gera a versão estática da loja para o GitHub Pages em site/.

Sem servidor: vitrine, catálogo, peças, ajuda e sacola. A sacola calcula frete no
navegador e fecha o pedido pelo WhatsApp. Painel, Pix automático, cupons e
pedidos registrados existem só na versão com servidor.

Uso: uv run python scripts/exportar_pages.py [--base /scheid-wear] [--url https://...]
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "site"


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--base", default="/scheid-wear")
    args.add_argument("--url", default="https://vampira-lady-gacha.github.io/scheid-wear")
    opcoes = args.parse_args()
    base = opcoes.base.rstrip("/")

    # Banco descartável com o catálogo inicial; precisa vir antes de importar o app.
    dados = tempfile.mkdtemp(prefix="scheid-pages-")
    os.environ.update(LOJA_DADOS=dados, LOJA_ESTATICO="1", LOJA_BASE=base, URL_PUBLICA=opcoes.url,
                      ADMIN_SENHA="nao-usada-no-site-estatico")
    sys.path.insert(0, str(RAIZ))

    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from app import config
    from app.db import SessaoLocal
    from app.main import app
    from app.models import Peca
    from app.seed import preparar

    preparar()
    with SessaoLocal() as sessao:
        slugs = list(sessao.scalars(select(Peca.slug).where(Peca.ativa.is_(True))))

    paginas = {"/": "index.html", "/catalogo": "catalogo/index.html", "/ajuda": "ajuda/index.html",
               "/sacola": "sacola/index.html"}
    paginas.update({f"/peca/{s}": f"peca/{s}/index.html" for s in slugs})

    def com_base(html: str) -> str:
        # Caminhos absolutos do site ganham o prefixo do Pages; links externos ficam como estão.
        return re.sub(r'((?:href|src|action|data-miniatura)=")/(?!/)', rf"\1{base}/", html)

    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    with TestClient(app) as cliente:
        for rota, arquivo in paginas.items():
            resp = cliente.get(rota)
            resp.raise_for_status()
            destino = SAIDA / arquivo
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(com_base(resp.text), encoding="utf-8")
            print("ok", rota)
        resp = cliente.get("/pagina-que-nao-existe")
        (SAIDA / "404.html").write_text(com_base(resp.text), encoding="utf-8")

    shutil.copytree(RAIZ / "static", SAIDA / "static")
    shutil.copytree(config.PASTA_UPLOADS, SAIDA / "media")
    fontes = SAIDA / "static" / "css" / "fontes.css"
    fontes.write_text(fontes.read_text(encoding="utf-8").replace("url('/static/", f"url('{base}/static/"), encoding="utf-8")
    (SAIDA / ".nojekyll").write_text("", encoding="utf-8")
    shutil.rmtree(dados, ignore_errors=True)
    print(f"Site estático em {SAIDA}")


if __name__ == "__main__":
    main()
