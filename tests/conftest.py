import os
import re
import tempfile

# Banco e uploads isolados: precisa vir antes de importar o app.
_PASTA = tempfile.mkdtemp(prefix="scheid-teste-")
os.environ["LOJA_DADOS"] = _PASTA
os.environ["ADMIN_EMAIL"] = "teste@scheid.com"
os.environ["ADMIN_SENHA"] = "senha-de-teste"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessaoLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import preparar  # noqa: E402


@pytest.fixture()
def cliente():
    Base.metadata.drop_all(engine)
    preparar()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def sessao(cliente):
    with SessaoLocal() as s:
        yield s


def csrf_de(html: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


@pytest.fixture()
def admin(cliente):
    pagina = cliente.get("/admin/entrar")
    resp = cliente.post(
        "/admin/entrar",
        data={"email": "teste@scheid.com", "senha": "senha-de-teste", "csrf": csrf_de(pagina.text)},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return cliente


ENDERECO = {
    "nome": "Maria Souza",
    "email": "maria@exemplo.com",
    "whatsapp": "(11) 98888-7777",
    "cep": "01310-100",
    "rua": "Avenida Paulista",
    "numero": "1000",
    "complemento": "",
    "bairro": "Bela Vista",
    "cidade": "São Paulo",
    "uf": "SP",
}
