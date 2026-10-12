"""Regras da loja: configurações, preço, frete, cupom, pedido, estoque, Pix e WhatsApp."""

import hashlib
import hmac
import re
import secrets
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO
from urllib.parse import quote

import segno
from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import config
from app.models import PAGAMENTOS, UFS, Configuracao, Cupom, ItemPedido, Pedido, Peca, Usuario, Variante

# ---------------------------------------------------------------- configurações

WHATSAPP_EXEMPLO = "5511900000000"

PADROES = {
    "nome_loja": "SCHEID",
    "linha": "STREETWEAR • SPORT • CULTURE",
    "bordao": "VISTA O SEU MOVIMENTO.",
    "drop_codigo": "DROP 001",
    "drop_nome": "AFTER HOURS",
    "drop_texto": "Inspirado na cidade, na noite e na liberdade de ser quem você é. Peças feitas para o seu dia, do seu jeito.",
    "whatsapp": WHATSAPP_EXEMPLO,
    "instagram": "scheidwear",
    "email": "",
    "pix_chave": "",
    "pix_nome": "SCHEID",
    "pix_cidade": "BRASIL",
    "frete_fixo": "24,90",
    "frete_gratis_acima": "299,00",
    "prazo_postagem": "Postamos em até 3 dias úteis depois da confirmação do pagamento.",
    "texto_envio": "Enviamos para todo o Brasil pelos Correios. O código de rastreio aparece na página do seu pedido assim que a peça for postada.",
    "texto_trocas": "Você tem 7 dias após o recebimento para desistir da compra ou trocar o tamanho. A peça precisa estar sem uso e com a etiqueta. Chame no WhatsApp com o código do pedido.",
    "texto_pagamento": "Pagamento por Pix: o QR Code e o código copia-e-cola aparecem logo depois de fechar o pedido, com o valor exato. Conferimos o pagamento e avisamos quando a peça for postada.",
    "exemplo_revisado": "",
}

GRUPOS_CONFIG = {
    "Marca e drop": {
        "nome_loja": "Nome da loja",
        "linha": "Linha abaixo do nome",
        "bordao": "Bordão",
        "drop_codigo": "Código do drop atual (ex.: DROP 001)",
        "drop_nome": "Nome do drop atual",
        "drop_texto": "Texto: sobre o drop",
    },
    "Contato": {
        "whatsapp": "WhatsApp que recebe os pedidos (com 55 e DDD, só números)",
        "instagram": "Usuário do Instagram (sem @)",
        "email": "E-mail de contato (opcional)",
    },
    "Pix": {
        "pix_chave": "Chave Pix (e-mail, CPF/CNPJ, telefone com +55 ou chave aleatória)",
        "pix_nome": "Nome do recebedor (como no banco)",
        "pix_cidade": "Cidade do recebedor",
    },
    "Frete": {
        "frete_fixo": "Frete fixo para todo o Brasil (R$)",
        "frete_gratis_acima": "Frete grátis a partir de (R$, vazio = nunca)",
        "prazo_postagem": "Prazo de postagem",
    },
    "Textos de ajuda": {
        "texto_envio": "Texto: envio",
        "texto_pagamento": "Texto: pagamento",
        "texto_trocas": "Texto: trocas e devoluções",
    },
}
ROTULOS_CONFIG = {chave: rotulo for grupo in GRUPOS_CONFIG.values() for chave, rotulo in grupo.items()}

# Símbolos de lavagem que o painel oferece. O desenho de cada um está em _icones.html.
CUIDADOS = {
    "lavar-30": "Lavar a até 30 °C",
    "lavar-mao": "Lavar à mão",
    "nao-alvejar": "Não alvejar",
    "nao-secadora": "Não usar secadora",
    "secar-sombra": "Secar à sombra",
    "passar-baixo": "Passar em temperatura baixa",
    "nao-passar": "Não passar",
    "nao-lavar-seco": "Não lavar a seco",
}


def ler_config(sessao: Session) -> dict[str, str]:
    valores = dict(PADROES)
    for item in sessao.scalars(select(Configuracao)):
        valores[item.chave] = item.valor
    return valores


def salvar_config(sessao: Session, novos: dict[str, str]) -> None:
    for chave, valor in novos.items():
        if chave not in PADROES:
            continue
        valor = valor.strip()
        if chave == "whatsapp":
            valor = so_digitos(valor)
        if chave == "instagram":
            valor = valor.lstrip("@")
        if chave in ("frete_fixo", "frete_gratis_acima"):
            centavos = ler_centavos(valor)
            valor = "" if centavos is None else f"{centavos / 100:.2f}".replace(".", ",")
        if chave == "pix_chave":
            valor = normalizar_chave_pix(valor)
        item = sessao.get(Configuracao, chave)
        if item is None:
            sessao.add(Configuracao(chave=chave, valor=valor))
        else:
            item.valor = valor
    sessao.commit()


# ---------------------------------------------------------------- utilidades


def so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()


def slugificar(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", sem_acento(texto).lower()).strip("-") or "peca"


def slug_unico(sessao: Session, texto: str, ignorar_id: int | None = None) -> str:
    base = slugificar(texto)
    slug, n = base, 2
    while True:
        existente = sessao.scalar(select(Peca).where(Peca.slug == slug))
        if existente is None or existente.id == ignorar_id:
            return slug
        slug, n = f"{base}-{n}", n + 1


def reais(centavos: int | None) -> str:
    if centavos is None:
        return ""
    inteiro, cent = divmod(abs(centavos), 100)
    milhar = f"{inteiro:,}".replace(",", ".")
    return f"{'-' if centavos < 0 else ''}R$ {milhar},{cent:02d}"


def ler_centavos(texto: str) -> int | None:
    """Aceita '189,90', '189.90', 'R$ 1.189,90' ou '189'. Vazio vira None."""
    texto = (texto or "").replace("R$", "").strip()
    if not texto:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        valor = round(float(texto) * 100)
    except ValueError as erro:
        raise ValueError(f"Valor inválido: {texto!r}") from erro
    if valor < 0:
        raise ValueError("Valor não pode ser negativo")
    return valor


def formatar_telefone(digitos: str) -> str:
    d = so_digitos(digitos)
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return digitos


def proximo_numero_peca(sessao: Session) -> int:
    ultimo = sessao.scalar(select(Peca.numero).order_by(Peca.numero.desc()).limit(1)) or 0
    return ultimo + 1


# ---------------------------------------------------------------- senhas


def gerar_hash(senha: str) -> str:
    sal = secrets.token_bytes(16)
    chave = hashlib.scrypt(senha.encode(), salt=sal, n=2**14, r=8, p=1)
    return f"scrypt${sal.hex()}${chave.hex()}"


def conferir_senha(senha: str, guardado: str) -> bool:
    try:
        _, sal, chave = guardado.split("$")
    except ValueError:
        return False
    calculado = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal), n=2**14, r=8, p=1)
    return hmac.compare_digest(calculado.hex(), chave)


def autenticar(sessao: Session, email: str, senha: str) -> Usuario | None:
    usuario = sessao.scalar(select(Usuario).where(Usuario.email == email.strip().lower()))
    if usuario and conferir_senha(senha, usuario.senha_hash):
        return usuario
    return None


# ---------------------------------------------------------------- fotos


def salvar_foto(conteudo: bytes) -> str:
    """Normaliza a foto (orientação, tamanho, JPEG) e devolve o nome do arquivo."""
    if len(conteudo) > config.TAMANHO_MAX_FOTO:
        raise ValueError("Foto maior que 8 MB")
    try:
        imagem = Image.open(BytesIO(conteudo))
        imagem = ImageOps.exif_transpose(imagem).convert("RGB")
    except Exception as erro:  # Pillow levanta vários tipos
        raise ValueError("Arquivo não é uma imagem válida (use JPG, PNG ou WebP)") from erro
    imagem.thumbnail((config.LADO_MAX_FOTO, config.LADO_MAX_FOTO))
    config.PASTA_UPLOADS.mkdir(parents=True, exist_ok=True)
    nome = f"{uuid.uuid4().hex}.jpg"
    imagem.save(config.PASTA_UPLOADS / nome, "JPEG", quality=84, optimize=True, progressive=True)
    return nome


def apagar_arquivo_foto(nome: str) -> None:
    caminho = config.PASTA_UPLOADS / nome
    if caminho.is_file():
        caminho.unlink()


# ---------------------------------------------------------------- cupom e frete


def buscar_cupom(sessao: Session, codigo: str) -> Cupom | None:
    codigo = codigo.strip().upper()
    if not codigo:
        return None
    return sessao.scalar(select(Cupom).where(Cupom.codigo == codigo))


def problema_cupom(cupom: Cupom | None, subtotal: int) -> str | None:
    """Devolve o motivo de o cupom não valer, ou None quando vale."""
    if cupom is None or not cupom.ativo:
        return "Cupom não encontrado."
    if cupom.validade and cupom.validade < date.today():
        return "Esse cupom venceu."
    if cupom.limite_usos is not None and cupom.usos >= cupom.limite_usos:
        return "Esse cupom já foi usado o máximo de vezes."
    if subtotal < cupom.minimo:
        return f"Esse cupom vale para compras a partir de {reais(cupom.minimo)}."
    return None


def desconto_cupom(cupom: Cupom, subtotal: int) -> int:
    if cupom.tipo == "percentual":
        return min(subtotal, round(subtotal * min(cupom.valor, 100) / 100))
    return min(subtotal, cupom.valor)


def calcular_frete(loja: dict[str, str], valor: int) -> int:
    fixo = ler_centavos(loja.get("frete_fixo", "")) or 0
    gratis = ler_centavos(loja.get("frete_gratis_acima", ""))
    if gratis is not None and gratis > 0 and valor >= gratis:
        return 0
    return fixo


# ---------------------------------------------------------------- cotação e pedido


class ErroPedido(ValueError):
    pass


@dataclass
class Linha:
    variante: Variante
    quantidade: int
    preco_unitario: int

    @property
    def subtotal(self) -> int:
        return self.quantidade * self.preco_unitario


@dataclass
class Cotacao:
    linhas: list[Linha] = field(default_factory=list)
    removidos: list[int] = field(default_factory=list)
    cupom: Cupom | None = None
    erro_cupom: str | None = None
    desconto: int = 0
    frete: int = 0
    frete_gratis_acima: int | None = None

    @property
    def quantidade(self) -> int:
        return sum(l.quantidade for l in self.linhas)

    @property
    def subtotal(self) -> int:
        return sum(l.subtotal for l in self.linhas)

    @property
    def total(self) -> int:
        return self.subtotal - self.desconto + self.frete

    @property
    def falta_frete_gratis(self) -> int | None:
        if not self.frete_gratis_acima or not self.frete:
            return None
        return max(0, self.frete_gratis_acima - (self.subtotal - self.desconto))


def cotar(sessao: Session, itens: list[tuple[int, int]], loja: dict[str, str], codigo_cupom: str = "") -> Cotacao:
    """Calcula preço, desconto e frete a partir de (variante_id, quantidade). O servidor é a fonte do preço."""
    quantidades: dict[int, int] = {}
    for variante_id, qtd in itens:
        if qtd > 0:
            quantidades[variante_id] = quantidades.get(variante_id, 0) + qtd

    variantes = {
        v.id: v
        for v in sessao.scalars(
            select(Variante)
            .where(Variante.id.in_(quantidades))
            .options(selectinload(Variante.peca).selectinload(Peca.fotos))
        )
    }
    cotacao = Cotacao(frete_gratis_acima=ler_centavos(loja.get("frete_gratis_acima", "")))
    for variante_id, qtd in quantidades.items():
        variante = variantes.get(variante_id)
        if variante is None or not variante.peca.ativa:
            cotacao.removidos.append(variante_id)
            continue
        cotacao.linhas.append(Linha(variante, min(qtd, 99), variante.peca.preco))

    if codigo_cupom.strip() and cotacao.linhas:
        cupom = buscar_cupom(sessao, codigo_cupom)
        motivo = problema_cupom(cupom, cotacao.subtotal)
        if motivo:
            cotacao.erro_cupom = motivo
        else:
            cotacao.cupom = cupom
            cotacao.desconto = desconto_cupom(cupom, cotacao.subtotal)
    if cotacao.linhas:
        cotacao.frete = calcular_frete(loja, cotacao.subtotal - cotacao.desconto)
    return cotacao


def proximo_codigo(sessao: Session) -> str:
    ultimo = sessao.scalar(select(Pedido.id).order_by(Pedido.id.desc()).limit(1)) or 0
    return f"SCD-{ultimo + 1:04d}"


@dataclass
class DadosEntrega:
    nome: str
    email: str
    whatsapp: str
    cep: str
    rua: str
    numero: str
    complemento: str
    bairro: str
    cidade: str
    uf: str
    observacao: str = ""

    def validar(self) -> None:
        if len(self.nome.strip()) < 3 or " " not in self.nome.strip():
            raise ErroPedido("Informe seu nome e sobrenome.")
        if len(so_digitos(self.whatsapp)) < 10:
            raise ErroPedido("Informe um WhatsApp com DDD.")
        if self.email.strip() and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", self.email.strip()):
            raise ErroPedido("Confira o e-mail.")
        if len(so_digitos(self.cep)) != 8:
            raise ErroPedido("Informe o CEP com 8 números.")
        if not self.rua.strip():
            raise ErroPedido("Informe a rua.")
        if not self.numero.strip():
            raise ErroPedido("Informe o número (ou S/N).")
        if not self.bairro.strip():
            raise ErroPedido("Informe o bairro.")
        if not self.cidade.strip():
            raise ErroPedido("Informe a cidade.")
        if self.uf.strip().upper() not in UFS:
            raise ErroPedido("Escolha o estado.")


def criar_pedido(
    sessao: Session,
    itens: list[tuple[int, int]],
    entrega: DadosEntrega,
    *,
    loja: dict[str, str],
    pagamento: str = "pix",
    cupom: str = "",
) -> Pedido:
    entrega.validar()
    if pagamento not in PAGAMENTOS:
        raise ErroPedido("Escolha a forma de pagamento.")

    cotacao = cotar(sessao, itens, loja, cupom)
    if not cotacao.linhas:
        raise ErroPedido("Sua sacola está vazia.")
    if cotacao.erro_cupom:
        raise ErroPedido(cotacao.erro_cupom)
    faltando = [l for l in cotacao.linhas if l.quantidade > l.variante.estoque]
    if faltando:
        l = faltando[0]
        if l.variante.estoque <= 0:
            raise ErroPedido(f"{l.variante.peca.nome} ({l.variante.tamanho}) esgotou. Tire da sacola para continuar.")
        raise ErroPedido(
            f"{l.variante.peca.nome} ({l.variante.tamanho}): só temos {l.variante.estoque} em estoque."
        )

    pedido = Pedido(
        codigo=proximo_codigo(sessao),
        nome=entrega.nome.strip()[:120],
        email=entrega.email.strip().lower()[:160],
        whatsapp=so_digitos(entrega.whatsapp)[:20],
        cep=so_digitos(entrega.cep),
        rua=entrega.rua.strip()[:160],
        numero=entrega.numero.strip()[:20],
        complemento=entrega.complemento.strip()[:80],
        bairro=entrega.bairro.strip()[:80],
        cidade=entrega.cidade.strip()[:80],
        uf=entrega.uf.strip().upper(),
        observacao=entrega.observacao.strip()[:1000],
        pagamento=pagamento,
        cupom=cotacao.cupom.codigo if cotacao.cupom else "",
        subtotal=cotacao.subtotal,
        desconto=cotacao.desconto,
        frete=cotacao.frete,
        total=cotacao.total,
    )
    for linha in cotacao.linhas:
        v = linha.variante
        v.estoque -= linha.quantidade
        pedido.itens.append(
            ItemPedido(
                variante_id=v.id,
                nome=v.peca.nome,
                numero=v.peca.numero,
                cor=v.cor,
                tamanho=v.tamanho,
                quantidade=linha.quantidade,
                preco_unitario=linha.preco_unitario,
            )
        )
    if cotacao.cupom:
        cotacao.cupom.usos += 1
    sessao.add(pedido)
    sessao.commit()
    return pedido


def mudar_status(sessao: Session, pedido: Pedido, novo: str) -> None:
    """Cancelar devolve as peças ao estoque; sair de cancelado retira de novo."""
    if novo == pedido.status:
        return
    if novo == "cancelado":
        sinal = 1
    elif pedido.status == "cancelado":
        sinal = -1
    else:
        sinal = 0
    if sinal:
        for item in pedido.itens:
            if item.variante_id and (v := sessao.get(Variante, item.variante_id)):
                v.estoque = max(0, v.estoque + sinal * item.quantidade)
    if novo in ("pago", "enviado", "entregue") and pedido.pago_em is None:
        pedido.pago_em = datetime.now()
    if novo in ("enviado", "entregue") and pedido.enviado_em is None:
        pedido.enviado_em = datetime.now()
    pedido.status = novo
    sessao.commit()


# ---------------------------------------------------------------- WhatsApp


def mensagem_whatsapp(pedido: Pedido, loja: dict[str, str]) -> str:
    linhas = [f"Olá, {loja['nome_loja']}! Fiz o pedido *{pedido.codigo}* no site:", ""]
    for item in pedido.itens:
        linhas.append(f"• {item.quantidade}x {item.nome} · {item.cor} · {item.tamanho} · {reais(item.preco_unitario)}")
    linhas.append("")
    if pedido.desconto:
        linhas.append(f"Cupom {pedido.cupom}: -{reais(pedido.desconto)}")
    linhas += [
        f"Frete: {reais(pedido.frete) if pedido.frete else 'grátis'}",
        f"*Total: {reais(pedido.total)}*",
        f"Pagamento: {PAGAMENTOS[pedido.pagamento]}",
        "",
        f"Nome: {pedido.nome}",
        f"Entrega: {pedido.endereco_linha}",
    ]
    if pedido.observacao:
        linhas.append(f"Obs.: {pedido.observacao}")
    return "\n".join(linhas)


def link_whatsapp(numero: str, texto: str = "") -> str:
    base = f"https://wa.me/{so_digitos(numero)}"
    return f"{base}?text={quote(texto)}" if texto else base


# ---------------------------------------------------------------- Pix (BR Code estático)


def normalizar_chave_pix(chave: str) -> str:
    chave = chave.strip()
    if not chave:
        return ""
    if "@" in chave:
        return chave.lower()
    if chave.startswith("+"):
        return "+" + so_digitos(chave)
    if re.fullmatch(r"[\d.\-/ ()]+", chave):
        return so_digitos(chave)
    return chave


def _campo(identificador: str, valor: str) -> str:
    return f"{identificador}{len(valor):02d}{valor}"


def _crc16(dados: str) -> str:
    crc = 0xFFFF
    for byte in dados.encode():
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def _texto_pix(texto: str, limite: int) -> str:
    return re.sub(r"[^A-Z0-9 ]", "", sem_acento(texto).upper()).strip()[:limite] or "SCHEID"


def payload_pix(chave: str, valor: int, nome: str, cidade: str, txid: str) -> str:
    """Monta o código 'copia e cola' do Pix (padrão EMV do Banco Central) com valor fixo."""
    conta = _campo("00", "br.gov.bcb.pix") + _campo("01", chave)
    corpo = (
        _campo("00", "01")
        + _campo("26", conta)
        + _campo("52", "0000")
        + _campo("53", "986")
        + _campo("54", f"{valor / 100:.2f}")
        + _campo("58", "BR")
        + _campo("59", _texto_pix(nome, 25))
        + _campo("60", _texto_pix(cidade, 15))
        + _campo("62", _campo("05", re.sub(r"[^A-Za-z0-9]", "", txid)[:25] or "***"))
        + "6304"
    )
    return corpo + _crc16(corpo)


def qr_svg(conteudo: str) -> str:
    return segno.make(conteudo, error="m").svg_inline(
        scale=4, border=0, dark="#0c0c0d", light=None, omitsize=True
    )


def pix_do_pedido(pedido: Pedido, loja: dict[str, str]) -> dict[str, str] | None:
    if pedido.pagamento != "pix" or not loja.get("pix_chave"):
        return None
    codigo = payload_pix(loja["pix_chave"], pedido.total, loja["pix_nome"], loja["pix_cidade"], pedido.codigo)
    return {"codigo": codigo, "qr": qr_svg(codigo)}
