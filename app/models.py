"""Tabelas da loja. Valores em centavos (inteiros) para não errar arredondamento."""

import secrets
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

TAMANHOS_PADRAO = ["PP", "P", "M", "G", "GG", "XG", "U"]

STATUS_PEDIDO = {
    "aguardando": "Aguardando pagamento",
    "pago": "Pago",
    "enviado": "Enviado",
    "entregue": "Entregue",
    "cancelado": "Cancelado",
}

PAGAMENTOS = {
    "pix": "Pix",
    "whatsapp": "Combinar no WhatsApp",
}

UFS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
]


class Categoria(Base):
    __tablename__ = "categoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(90), unique=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    pecas: Mapped[list["Peca"]] = relationship(back_populates="categoria")


class Peca(Base):
    __tablename__ = "peca"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[int] = mapped_column(Integer, default=0)
    nome: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True)
    descricao: Mapped[str] = mapped_column(Text, default="")
    material: Mapped[str] = mapped_column(String(120), default="")
    # Códigos dos símbolos de lavagem separados por vírgula (ver CUIDADOS em servicos.py).
    cuidados: Mapped[str] = mapped_column(String(200), default="")
    medidas: Mapped[str] = mapped_column(Text, default="")
    drop: Mapped[str] = mapped_column(String(40), default="")
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categoria.id", ondelete="SET NULL"))
    preco: Mapped[int] = mapped_column(Integer)
    preco_de: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    destaque: Mapped[bool] = mapped_column(Boolean, default=False)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    categoria: Mapped[Categoria | None] = relationship(back_populates="pecas")
    fotos: Mapped[list["Foto"]] = relationship(
        back_populates="peca", cascade="all, delete-orphan", order_by="Foto.ordem"
    )
    variantes: Mapped[list["Variante"]] = relationship(
        back_populates="peca", cascade="all, delete-orphan", order_by="Variante.id"
    )

    @property
    def numero_fmt(self) -> str:
        return f"Nº {self.numero:03d}"

    @property
    def foto_capa(self) -> "Foto | None":
        return self.fotos[0] if self.fotos else None

    @property
    def estoque_total(self) -> int:
        return sum(v.estoque for v in self.variantes)

    @property
    def esgotada(self) -> bool:
        return self.estoque_total <= 0

    @property
    def cores(self) -> list[tuple[str, str]]:
        vistas: dict[str, str] = {}
        for v in self.variantes:
            vistas.setdefault(v.cor, v.cor_hex)
        return list(vistas.items())

    @property
    def tamanhos(self) -> list[str]:
        presentes = {v.tamanho for v in self.variantes}
        ordem = [t for t in TAMANHOS_PADRAO if t in presentes]
        return ordem + sorted(presentes - set(ordem))

    @property
    def variantes_json(self) -> list[dict]:
        return [{"id": v.id, "cor": v.cor, "tamanho": v.tamanho, "estoque": v.estoque} for v in self.variantes]

    @property
    def tabela_medidas(self) -> list[list[str]]:
        """Linhas 'Tam | Largura | Comprimento' viram uma tabela; a primeira é o cabeçalho."""
        linhas = [[c.strip() for c in l.split("|")] for l in self.medidas.splitlines() if l.strip()]
        return linhas if len(linhas) >= 2 else []

    @property
    def lista_cuidados(self) -> list[str]:
        return [c.strip() for c in self.cuidados.split(",") if c.strip()]

    def tamanhos_disponiveis(self) -> set[str]:
        return {v.tamanho for v in self.variantes if v.estoque > 0}


class Foto(Base):
    __tablename__ = "foto"

    id: Mapped[int] = mapped_column(primary_key=True)
    peca_id: Mapped[int] = mapped_column(ForeignKey("peca.id", ondelete="CASCADE"))
    arquivo: Mapped[str] = mapped_column(String(200))
    ordem: Mapped[int] = mapped_column(Integer, default=0)

    peca: Mapped[Peca] = relationship(back_populates="fotos")


class Variante(Base):
    __tablename__ = "variante"
    __table_args__ = (UniqueConstraint("peca_id", "cor", "tamanho"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    peca_id: Mapped[int] = mapped_column(ForeignKey("peca.id", ondelete="CASCADE"))
    cor: Mapped[str] = mapped_column(String(40))
    cor_hex: Mapped[str] = mapped_column(String(7), default="#0c0c0d")
    tamanho: Mapped[str] = mapped_column(String(10))
    estoque: Mapped[int] = mapped_column(Integer, default=0)

    peca: Mapped[Peca] = relationship(back_populates="variantes")


class Cupom(Base):
    __tablename__ = "cupom"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    # "percentual": valor é a porcentagem (10 = 10%). "valor": valor em centavos.
    tipo: Mapped[str] = mapped_column(String(12), default="percentual")
    valor: Mapped[int] = mapped_column(Integer)
    minimo: Mapped[int] = mapped_column(Integer, default=0)
    limite_usos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usos: Mapped[int] = mapped_column(Integer, default=0)
    validade: Mapped[date | None] = mapped_column(Date, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Pedido(Base):
    __tablename__ = "pedido"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    # Vai no link de acompanhamento para ninguém abrir o pedido de outra pessoa pelo código.
    token: Mapped[str] = mapped_column(String(32), default=lambda: secrets.token_urlsafe(12))
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), default="")
    whatsapp: Mapped[str] = mapped_column(String(20))
    cep: Mapped[str] = mapped_column(String(8))
    rua: Mapped[str] = mapped_column(String(160))
    numero: Mapped[str] = mapped_column(String(20))
    complemento: Mapped[str] = mapped_column(String(80), default="")
    bairro: Mapped[str] = mapped_column(String(80))
    cidade: Mapped[str] = mapped_column(String(80))
    uf: Mapped[str] = mapped_column(String(2))
    observacao: Mapped[str] = mapped_column(Text, default="")
    pagamento: Mapped[str] = mapped_column(String(12), default="pix")
    cupom: Mapped[str] = mapped_column(String(30), default="")
    subtotal: Mapped[int] = mapped_column(Integer)
    desconto: Mapped[int] = mapped_column(Integer, default=0)
    frete: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="aguardando")
    rastreio: Mapped[str] = mapped_column(String(40), default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    pago_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    itens: Mapped[list["ItemPedido"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan", order_by="ItemPedido.id"
    )

    @property
    def quantidade_pecas(self) -> int:
        return sum(i.quantidade for i in self.itens)

    @property
    def cep_fmt(self) -> str:
        return f"{self.cep[:5]}-{self.cep[5:]}"

    @property
    def endereco_linha(self) -> str:
        comp = f", {self.complemento}" if self.complemento else ""
        return f"{self.rua}, {self.numero}{comp} · {self.bairro} · {self.cidade}/{self.uf} · CEP {self.cep_fmt}"


class ItemPedido(Base):
    """Guarda uma cópia de nome, cor, tamanho e preço: a peça pode mudar depois."""

    __tablename__ = "item_pedido"

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedido.id", ondelete="CASCADE"))
    variante_id: Mapped[int | None] = mapped_column(ForeignKey("variante.id", ondelete="SET NULL"))
    nome: Mapped[str] = mapped_column(String(120))
    numero: Mapped[int] = mapped_column(Integer, default=0)
    cor: Mapped[str] = mapped_column(String(40))
    tamanho: Mapped[str] = mapped_column(String(10))
    quantidade: Mapped[int] = mapped_column(Integer)
    preco_unitario: Mapped[int] = mapped_column(Integer)

    pedido: Mapped[Pedido] = relationship(back_populates="itens")

    @property
    def subtotal(self) -> int:
        return self.quantidade * self.preco_unitario


class Configuracao(Base):
    __tablename__ = "configuracao"

    chave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(Text, default="")


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True)
    nome: Mapped[str] = mapped_column(String(80))
    senha_hash: Mapped[str] = mapped_column(String(200))
