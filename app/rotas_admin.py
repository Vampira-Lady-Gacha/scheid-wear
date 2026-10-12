"""Painel da loja: peças, fotos, grade de estoque, categorias, pedidos, cupons e configurações."""

import time
from collections import defaultdict
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from starlette.datastructures import FormData

from app.db import obter_sessao
from app.models import STATUS_PEDIDO, Categoria, Cupom, Foto, Pedido, Peca, Usuario, Variante
from app.servicos import (
    CUIDADOS,
    GRUPOS_CONFIG,
    ROTULOS_CONFIG,
    WHATSAPP_EXEMPLO,
    apagar_arquivo_foto,
    autenticar,
    conferir_senha,
    gerar_hash,
    ler_centavos,
    ler_config,
    mudar_status,
    proximo_numero_peca,
    salvar_config,
    salvar_foto,
    slug_unico,
    slugificar,
)
from app.web import avisar, render

roteador = APIRouter(prefix="/admin")

ESTOQUE_BAIXO = 2
GRADE_INICIAL = ["P", "M", "G", "GG"]
_tentativas: dict[str, list[float]] = defaultdict(list)


class PrecisaEntrar(Exception):
    pass


def usuario_logado(request: Request, sessao: Session = Depends(obter_sessao)) -> Usuario:
    usuario_id = request.session.get("usuario_id")
    usuario = sessao.get(Usuario, usuario_id) if usuario_id else None
    if usuario is None:
        raise PrecisaEntrar()
    return usuario


async def formulario(request: Request) -> FormData:
    """Lê o formulário e confere o token CSRF de todo POST do painel."""
    dados = await request.form()
    if not request.session.get("csrf") or dados.get("csrf") != request.session["csrf"]:
        raise HTTPException(400, "Formulário expirado. Volte, recarregue a página e tente de novo.")
    return dados


def voltar(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


# ---------------------------------------------------------------- acesso


@roteador.get("/entrar")
def tela_entrar(request: Request, sessao: Session = Depends(obter_sessao)):
    return render(request, sessao, "admin/entrar.html", {"erro": None})


@roteador.post("/entrar")
async def entrar(request: Request, sessao: Session = Depends(obter_sessao)):
    dados = await formulario(request)
    ip = request.client.host if request.client else "?"
    agora = time.monotonic()
    _tentativas[ip] = [t for t in _tentativas[ip] if agora - t < 600]
    if len(_tentativas[ip]) >= 8:
        return render(request, sessao, "admin/entrar.html", {"erro": "Muitas tentativas. Espere 10 minutos."}, 429)
    usuario = autenticar(sessao, str(dados.get("email", "")), str(dados.get("senha", "")))
    if usuario is None:
        _tentativas[ip].append(agora)
        return render(request, sessao, "admin/entrar.html", {"erro": "E-mail ou senha não conferem."}, 401)
    _tentativas.pop(ip, None)
    request.session.clear()
    request.session["usuario_id"] = usuario.id
    return voltar("/admin")


@roteador.post("/sair")
async def sair(request: Request):
    await formulario(request)
    request.session.clear()
    return voltar("/admin/entrar")


@roteador.get("/conta")
def tela_conta(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    return render(request, sessao, "admin/conta.html", {"usuario": usuario, "erro": None})


@roteador.post("/conta")
async def salvar_conta(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    dados = await formulario(request)
    atual, nova = str(dados.get("senha_atual", "")), str(dados.get("senha_nova", ""))
    erro = None
    if not conferir_senha(atual, usuario.senha_hash):
        erro = "A senha atual não confere."
    elif len(nova) < 8:
        erro = "A nova senha precisa de pelo menos 8 caracteres."
    elif nova != dados.get("senha_confirma"):
        erro = "A confirmação não é igual à nova senha."
    if erro:
        return render(request, sessao, "admin/conta.html", {"usuario": usuario, "erro": erro}, 422)
    usuario.senha_hash = gerar_hash(nova)
    sessao.commit()
    avisar(request, "Senha alterada.")
    return voltar("/admin/conta")


# ---------------------------------------------------------------- visão geral


@roteador.get("")
def painel(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    def pedidos_com(status: str) -> list[Pedido]:
        return list(
            sessao.scalars(
                select(Pedido).where(Pedido.status == status).options(selectinload(Pedido.itens)).order_by(Pedido.id.desc())
            )
        )

    inicio_mes = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    vendido_mes = sessao.scalar(
        select(func.coalesce(func.sum(Pedido.total), 0)).where(
            Pedido.status.in_(["pago", "enviado", "entregue"]), Pedido.criado_em >= inicio_mes
        )
    )
    pedidos_7d = sessao.scalar(
        select(func.count(Pedido.id)).where(Pedido.criado_em >= datetime.now() - timedelta(days=7))
    )
    baixo = list(
        sessao.scalars(
            select(Variante)
            .join(Peca)
            .where(Peca.ativa.is_(True), Variante.estoque <= ESTOQUE_BAIXO)
            .options(selectinload(Variante.peca))
            .order_by(Variante.estoque, Peca.nome)
        )
    )
    loja = ler_config(sessao)
    return render(
        request,
        sessao,
        "admin/painel.html",
        {
            "usuario": usuario,
            "aguardando": pedidos_com("aguardando"),
            "a_enviar": pedidos_com("pago"),
            "vendido_mes": vendido_mes,
            "pedidos_7d": pedidos_7d,
            "baixo": baixo,
            "whatsapp_exemplo": loja["whatsapp"] == WHATSAPP_EXEMPLO,
            "sem_pix": not loja["pix_chave"],
            "ha_exemplo": not loja["exemplo_revisado"]
            and sessao.scalar(select(func.count(Foto.id)).where(Foto.arquivo.like("drop001-%"))),
        },
    )


@roteador.post("/exemplo-revisado")
async def exemplo_revisado(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    await formulario(request)
    salvar_config(sessao, {"exemplo_revisado": "1"})
    return voltar("/admin")


# ---------------------------------------------------------------- peças


@roteador.get("/pecas")
def lista_pecas(
    request: Request, q: str = "", usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    consulta = select(Peca).options(selectinload(Peca.fotos), selectinload(Peca.variantes), selectinload(Peca.categoria))
    if q.strip():
        termo = f"%{q.strip()}%"
        consulta = consulta.where(Peca.nome.ilike(termo) | Peca.drop.ilike(termo))
    pecas = list(sessao.scalars(consulta.order_by(Peca.ativa.desc(), Peca.ordem, Peca.numero)))
    return render(request, sessao, "admin/pecas.html", {"usuario": usuario, "pecas": pecas, "q": q})


def _categorias(sessao: Session) -> list[Categoria]:
    return list(sessao.scalars(select(Categoria).order_by(Categoria.ordem, Categoria.nome)))


def _contexto_form(sessao: Session, usuario: Usuario, peca: Peca | None, erro: str | None = None, dados=None) -> dict:
    contexto = {
        "usuario": usuario,
        "peca": peca,
        "categorias": _categorias(sessao),
        "erro": erro,
        "dados": dados or {},
        "proximo_numero": proximo_numero_peca(sessao),
    }
    if peca is not None:
        contexto.update(
            cores=peca.cores,
            tamanhos=peca.tamanhos,
            estoque={(v.cor, v.tamanho): v.estoque for v in peca.variantes},
        )
    return contexto


@roteador.get("/pecas/nova")
def nova_peca(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    return render(request, sessao, "admin/peca_form.html", _contexto_form(sessao, usuario, None))


def _aplicar_dados(sessao: Session, peca: Peca, dados: FormData) -> None:
    nome = str(dados.get("nome", "")).strip()
    if len(nome) < 2:
        raise ValueError("Dê um nome para a peça.")
    preco = ler_centavos(str(dados.get("preco", "")))
    if not preco:
        raise ValueError("Informe o preço.")
    preco_de = ler_centavos(str(dados.get("preco_de", "")))
    if preco_de is not None and preco_de <= preco:
        raise ValueError("O preço “de” precisa ser maior que o preço de venda (ou fique vazio).")
    numero = str(dados.get("numero", "")).strip()
    categoria_id = str(dados.get("categoria_id", ""))
    peca.nome = nome[:120]
    peca.slug = slug_unico(sessao, nome, peca.id)
    peca.numero = int(numero) if numero.isdigit() else (peca.numero or proximo_numero_peca(sessao))
    peca.drop = str(dados.get("drop", "")).strip().upper()[:40]
    peca.material = str(dados.get("material", "")).strip()[:120]
    peca.cuidados = ",".join(c for c in dados.getlist("cuidados") if c in CUIDADOS)
    peca.medidas = str(dados.get("medidas", "")).strip()
    peca.descricao = str(dados.get("descricao", "")).strip()
    peca.categoria_id = int(categoria_id) if categoria_id.isdigit() else None
    peca.preco = preco
    peca.preco_de = preco_de
    peca.ativa = dados.get("ativa") == "on"
    peca.destaque = dados.get("destaque") == "on"


@roteador.post("/pecas/nova")
async def criar_peca(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    dados = await formulario(request)
    peca = Peca(preco=0, numero=0)
    try:
        _aplicar_dados(sessao, peca, dados)
    except ValueError as erro:
        return render(request, sessao, "admin/peca_form.html", _contexto_form(sessao, usuario, None, str(erro), dados), 422)
    if peca.destaque:
        _tirar_outros_destaques(sessao)
    for tamanho in GRADE_INICIAL:
        peca.variantes.append(Variante(cor="Preto", cor_hex="#0c0c0d", tamanho=tamanho, estoque=0))
    sessao.add(peca)
    sessao.commit()
    avisar(request, "Peça criada. Agora envie as fotos e preencha o estoque da grade.")
    return voltar(f"/admin/pecas/{peca.id}")


def _tirar_outros_destaques(sessao: Session, manter: int | None = None) -> None:
    for outra in sessao.scalars(select(Peca).where(Peca.destaque.is_(True))):
        if outra.id != manter:
            outra.destaque = False


def _carregar_peca(sessao: Session, peca_id: int) -> Peca:
    peca = sessao.scalar(
        select(Peca).where(Peca.id == peca_id).options(selectinload(Peca.fotos), selectinload(Peca.variantes))
    )
    if peca is None:
        raise HTTPException(404)
    return peca


@roteador.get("/pecas/{peca_id}")
def editar_peca(
    peca_id: int, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    peca = _carregar_peca(sessao, peca_id)
    return render(request, sessao, "admin/peca_form.html", _contexto_form(sessao, usuario, peca))


@roteador.post("/pecas/{peca_id}")
async def salvar_peca(
    peca_id: int, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    dados = await formulario(request)
    peca = _carregar_peca(sessao, peca_id)
    try:
        _aplicar_dados(sessao, peca, dados)
    except ValueError as erro:
        sessao.rollback()
        peca = _carregar_peca(sessao, peca_id)
        return render(request, sessao, "admin/peca_form.html", _contexto_form(sessao, usuario, peca, str(erro), dados), 422)
    if peca.destaque:
        _tirar_outros_destaques(sessao, peca.id)
    sessao.commit()
    avisar(request, "Dados da peça salvos.")
    return voltar(f"/admin/pecas/{peca.id}")


@roteador.post("/pecas/{peca_id}/duplicar")
async def duplicar_peca(
    peca_id: int, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    """Copia dados e grade (com estoque zerado) para cadastrar uma variação parecida mais rápido."""
    await formulario(request)
    original = _carregar_peca(sessao, peca_id)
    copia = Peca(
        nome=f"{original.nome} (cópia)",
        slug=slug_unico(sessao, f"{original.nome} copia"),
        numero=proximo_numero_peca(sessao),
        drop=original.drop,
        material=original.material,
        cuidados=original.cuidados,
        medidas=original.medidas,
        descricao=original.descricao,
        categoria_id=original.categoria_id,
        preco=original.preco,
        preco_de=original.preco_de,
        ativa=False,
        ordem=original.ordem + 1,
    )
    for v in original.variantes:
        copia.variantes.append(Variante(cor=v.cor, cor_hex=v.cor_hex, tamanho=v.tamanho, estoque=0))
    sessao.add(copia)
    sessao.commit()
    avisar(request, "Cópia criada fora da loja, com estoque zerado. Ajuste nome, fotos e estoque e marque “Mostrar na loja”.")
    return voltar(f"/admin/pecas/{copia.id}")


@roteador.post("/pecas/{peca_id}/grade")
async def salvar_grade(
    peca_id: int, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    """Recria a grade cor × tamanho mantendo os ids das variantes que continuam."""
    dados = await formulario(request)
    peca = _carregar_peca(sessao, peca_id)
    tamanhos = [t.strip().upper() for t in str(dados.get("tamanhos", "")).replace(";", ",").split(",") if t.strip()]
    tamanhos = list(dict.fromkeys(tamanhos))[:12]
    nomes, hexas = dados.getlist("cor_nome"), dados.getlist("cor_hex")
    if not tamanhos:
        avisar(request, "Informe ao menos um tamanho na grade.")
        return voltar(f"/admin/pecas/{peca.id}#grade")

    existentes = {(v.cor, v.tamanho): v for v in peca.variantes}
    desejadas: set[tuple[str, str]] = set()
    for indice, (nome, hexa) in enumerate(zip(nomes, hexas)):
        nome = str(nome).strip()[:40]
        if not nome or dados.get(f"remover-{indice}") == "on":
            continue
        original = str(dados.get(f"cor_original-{indice}", nome))
        for tamanho in tamanhos:
            valor = str(dados.get(f"estoque-{indice}-{tamanho}", "0")).strip()
            qtd = max(0, int(valor)) if valor.lstrip("-").isdigit() else 0
            variante = existentes.get((original, tamanho)) or existentes.get((nome, tamanho))
            if variante is None:
                variante = Variante(tamanho=tamanho)
                peca.variantes.append(variante)
            variante.cor, variante.cor_hex, variante.estoque = nome, str(hexa)[:7] or "#0c0c0d", qtd
            desejadas.add((nome, tamanho))
    if not desejadas:
        avisar(request, "A peça precisa de pelo menos uma cor.")
        return voltar(f"/admin/pecas/{peca.id}#grade")
    for variante in list(peca.variantes):
        if (variante.cor, variante.tamanho) not in desejadas:
            peca.variantes.remove(variante)
    sessao.commit()
    avisar(request, "Grade e estoque salvos.")
    return voltar(f"/admin/pecas/{peca.id}#grade")


@roteador.post("/pecas/{peca_id}/fotos")
async def enviar_fotos(
    peca_id: int, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    dados = await formulario(request)
    peca = _carregar_peca(sessao, peca_id)
    arquivos = [a for a in dados.getlist("fotos") if isinstance(a, UploadFile) and a.filename]
    proxima = max((f.ordem for f in peca.fotos), default=-1) + 1
    erros, enviadas = [], 0
    for arquivo in arquivos[:12]:
        try:
            nome = salvar_foto(await arquivo.read())
        except ValueError as erro:
            erros.append(f"{arquivo.filename}: {erro}")
            continue
        peca.fotos.append(Foto(arquivo=nome, ordem=proxima))
        proxima += 1
        enviadas += 1
    sessao.commit()
    avisar(request, "; ".join(erros) if erros else f"{enviadas} foto(s) enviada(s).")
    return voltar(f"/admin/pecas/{peca.id}#fotos")


@roteador.post("/pecas/{peca_id}/fotos/{foto_id}/{acao}")
async def acao_foto(
    peca_id: int,
    foto_id: int,
    acao: str,
    request: Request,
    usuario: Usuario = Depends(usuario_logado),
    sessao: Session = Depends(obter_sessao),
):
    await formulario(request)
    peca = _carregar_peca(sessao, peca_id)
    foto = next((f for f in peca.fotos if f.id == foto_id), None)
    if foto is None:
        raise HTTPException(404)
    if acao == "apagar":
        peca.fotos.remove(foto)
        sessao.commit()
        apagar_arquivo_foto(foto.arquivo)
    elif acao == "capa":
        for posicao, f in enumerate([foto] + [f for f in peca.fotos if f is not foto]):
            f.ordem = posicao
        sessao.commit()
    else:
        raise HTTPException(404)
    return voltar(f"/admin/pecas/{peca.id}#fotos")


@roteador.post("/pecas/{peca_id}/apagar")
async def apagar_peca(
    peca_id: int, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    await formulario(request)
    peca = _carregar_peca(sessao, peca_id)
    arquivos = [f.arquivo for f in peca.fotos]
    sessao.delete(peca)
    sessao.commit()
    for nome in arquivos:
        apagar_arquivo_foto(nome)
    avisar(request, f"“{peca.nome}” apagada. Os pedidos antigos continuam com o registro da peça.")
    return voltar("/admin/pecas")


# ---------------------------------------------------------------- categorias


@roteador.get("/categorias")
def lista_categorias(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    contagem = dict(sessao.execute(select(Peca.categoria_id, func.count(Peca.id)).group_by(Peca.categoria_id)).all())
    return render(
        request,
        sessao,
        "admin/categorias.html",
        {"usuario": usuario, "categorias": _categorias(sessao), "contagem": contagem},
    )


@roteador.post("/categorias")
async def salvar_categorias(
    request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    dados = await formulario(request)
    for categoria in _categorias(sessao):
        if dados.get(f"apagar-{categoria.id}") == "on":
            sessao.delete(categoria)
            continue
        nome = str(dados.get(f"nome-{categoria.id}", categoria.nome)).strip()
        if nome:
            categoria.nome = nome[:80]
        ordem = str(dados.get(f"ordem-{categoria.id}", categoria.ordem))
        categoria.ordem = int(ordem) if ordem.lstrip("-").isdigit() else categoria.ordem
        categoria.ativa = dados.get(f"ativa-{categoria.id}") == "on"
    nova = str(dados.get("nova", "")).strip()
    if nova:
        slug, n = slugificar(nova), 2
        while sessao.scalar(select(Categoria).where(Categoria.slug == slug)):
            slug, n = f"{slugificar(nova)}-{n}", n + 1
        sessao.add(Categoria(nome=nova[:80], slug=slug, ordem=len(_categorias(sessao))))
    sessao.commit()
    avisar(request, "Categorias salvas.")
    return voltar("/admin/categorias")


# ---------------------------------------------------------------- pedidos


@roteador.get("/pedidos")
def lista_pedidos(
    request: Request,
    status: str = "",
    q: str = "",
    usuario: Usuario = Depends(usuario_logado),
    sessao: Session = Depends(obter_sessao),
):
    consulta = select(Pedido).options(selectinload(Pedido.itens)).order_by(Pedido.id.desc())
    if status in STATUS_PEDIDO:
        consulta = consulta.where(Pedido.status == status)
    if q.strip():
        termo = f"%{q.strip()}%"
        consulta = consulta.where(
            Pedido.nome.ilike(termo) | Pedido.codigo.ilike(termo) | Pedido.whatsapp.ilike(termo) | Pedido.email.ilike(termo)
        )
    contagem = dict(sessao.execute(select(Pedido.status, func.count(Pedido.id)).group_by(Pedido.status)).all())
    return render(
        request,
        sessao,
        "admin/pedidos.html",
        {"usuario": usuario, "pedidos": list(sessao.scalars(consulta.limit(300))), "status": status, "q": q, "contagem": contagem},
    )


def _carregar_pedido(sessao: Session, pedido_id: int) -> Pedido:
    pedido = sessao.scalar(select(Pedido).where(Pedido.id == pedido_id).options(selectinload(Pedido.itens)))
    if pedido is None:
        raise HTTPException(404)
    return pedido


@roteador.get("/pedidos/{pedido_id}")
def ver_pedido(
    pedido_id: int, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    return render(request, sessao, "admin/pedido.html", {"usuario": usuario, "pedido": _carregar_pedido(sessao, pedido_id)})


@roteador.post("/pedidos/{pedido_id}/status")
async def status_pedido(
    pedido_id: int, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    dados = await formulario(request)
    pedido = _carregar_pedido(sessao, pedido_id)
    novo = str(dados.get("status", ""))
    if novo not in STATUS_PEDIDO:
        raise HTTPException(404)
    mudar_status(sessao, pedido, novo)
    avisar(request, f"Pedido {pedido.codigo}: {STATUS_PEDIDO[novo].lower()}.")
    return voltar(f"/admin/pedidos/{pedido.id}")


@roteador.post("/pedidos/{pedido_id}/rastreio")
async def rastreio_pedido(
    pedido_id: int, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    dados = await formulario(request)
    pedido = _carregar_pedido(sessao, pedido_id)
    pedido.rastreio = str(dados.get("rastreio", "")).strip().upper()[:40]
    sessao.commit()
    if pedido.rastreio and pedido.status in ("aguardando", "pago"):
        mudar_status(sessao, pedido, "enviado")
        avisar(request, f"Rastreio salvo e pedido {pedido.codigo} marcado como enviado.")
    else:
        avisar(request, "Rastreio salvo.")
    return voltar(f"/admin/pedidos/{pedido.id}")


# ---------------------------------------------------------------- cupons


@roteador.get("/cupons")
def lista_cupons(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    cupons = list(sessao.scalars(select(Cupom).order_by(Cupom.ativo.desc(), Cupom.codigo)))
    return render(request, sessao, "admin/cupons.html", {"usuario": usuario, "cupons": cupons, "erro": None, "hoje": date.today()})


@roteador.post("/cupons")
async def criar_cupom(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    dados = await formulario(request)
    codigo = str(dados.get("codigo", "")).strip().upper().replace(" ", "")
    tipo = "valor" if dados.get("tipo") == "valor" else "percentual"
    erro = None
    try:
        if not codigo or len(codigo) > 30:
            raise ValueError("Informe um código de até 30 letras ou números.")
        if sessao.scalar(select(Cupom).where(Cupom.codigo == codigo)):
            raise ValueError(f"Já existe o cupom {codigo}.")
        if tipo == "percentual":
            texto = str(dados.get("valor", "")).replace("%", "").strip()
            valor = int(texto) if texto.isdigit() else 0
            if not 1 <= valor <= 100:
                raise ValueError("A porcentagem precisa ser de 1 a 100.")
        else:
            valor = ler_centavos(str(dados.get("valor", ""))) or 0
            if valor <= 0:
                raise ValueError("Informe o valor do desconto.")
        minimo = ler_centavos(str(dados.get("minimo", ""))) or 0
        limite = str(dados.get("limite_usos", "")).strip()
        validade = str(dados.get("validade", "")).strip()
        cupom = Cupom(
            codigo=codigo,
            tipo=tipo,
            valor=valor,
            minimo=minimo,
            limite_usos=int(limite) if limite.isdigit() else None,
            validade=date.fromisoformat(validade) if validade else None,
        )
    except ValueError as e:
        erro = str(e)
    if erro:
        cupons = list(sessao.scalars(select(Cupom).order_by(Cupom.ativo.desc(), Cupom.codigo)))
        return render(
            request, sessao, "admin/cupons.html", {"usuario": usuario, "cupons": cupons, "erro": erro, "hoje": date.today()}, 422
        )
    sessao.add(cupom)
    sessao.commit()
    avisar(request, f"Cupom {codigo} criado.")
    return voltar("/admin/cupons")


@roteador.post("/cupons/{cupom_id}/{acao}")
async def acao_cupom(
    cupom_id: int, acao: str, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    await formulario(request)
    cupom = sessao.get(Cupom, cupom_id)
    if cupom is None:
        raise HTTPException(404)
    if acao == "alternar":
        cupom.ativo = not cupom.ativo
        avisar(request, f"Cupom {cupom.codigo} {'ativado' if cupom.ativo else 'desativado'}.")
    elif acao == "apagar":
        sessao.delete(cupom)
        avisar(request, f"Cupom {cupom.codigo} apagado.")
    else:
        raise HTTPException(404)
    sessao.commit()
    return voltar("/admin/cupons")


# ---------------------------------------------------------------- configurações


@roteador.get("/configuracoes")
def tela_config(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    return render(request, sessao, "admin/configuracoes.html", {"usuario": usuario, "grupos": GRUPOS_CONFIG})


@roteador.post("/configuracoes")
async def gravar_config(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    dados = await formulario(request)
    try:
        salvar_config(sessao, {chave: str(dados.get(chave, "")) for chave in ROTULOS_CONFIG})
    except ValueError as erro:
        sessao.rollback()
        avisar(request, f"Nada foi salvo: {erro}")
        return voltar("/admin/configuracoes")
    avisar(request, "Configurações salvas.")
    return voltar("/admin/configuracoes")
