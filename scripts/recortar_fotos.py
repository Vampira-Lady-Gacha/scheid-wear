"""Recorta as artes do DROP 001 (fotos-originais/) em fotos de produto quadradas.

Fonte: imagens enviadas pela SCHEID (grade das 5 camisetas e a apresentação da
SCHEID BASIC). Cada recorte ganha margem no tom do fundo da arte para virar quadrado,
sem cortar a peça.

Uso: uv run python scripts/recortar_fotos.py
"""

from pathlib import Path

from PIL import Image, ImageFilter

RAIZ = Path(__file__).resolve().parent.parent
ORIGEM = RAIZ / "fotos-originais"
DESTINO = RAIZ / "static" / "img" / "drop001"
LARGURA = 1000
FUNDO_ARTE = (11, 11, 12)  # o preto das artes da marca

# Grade: uma linha por camiseta (y0, y1) e colunas frente, costas, manga, etiqueta interna, etiqueta lateral.
GRADE = "drop001-grade-camisetas.jpg"
LINHAS = {
    "scheid-basic": (88, 264),
    "after-hours": (268, 466),
    "scd-sport": (470, 656),
    "no-rules": (660, 839),
    "culture": (843, 1021),
}
COLUNAS = {"frente": (181, 541), "costas": (544, 907), "manga": (910, 1145)}
ETIQUETAS = {"etiqueta-interna": (1150, 1326), "etiqueta-lateral": (1331, 1510)}

APRESENTACAO = "drop001-scheid-basic-apresentacao.jpg"
RECORTES_APRESENTACAO = {
    "scheid-basic-mockup-frente": (245, 62, 712, 578),
    "scheid-basic-mockup-costas": (688, 62, 1122, 578),
    "scheid-basic-como-fica-1": (35, 626, 244, 916),
    "scheid-basic-como-fica-2": (252, 626, 433, 916),
    "scheid-basic-como-fica-3": (440, 626, 713, 916),
    "tags": (762, 662, 1010, 914),
    "embalagem": (1046, 662, 1365, 914),
}


def fundo(img: Image.Image) -> tuple[int, int, int]:
    """Cor média das bordas: é com ela que a foto ganha margem."""
    w, h = img.size
    borda = [img.getpixel((x, y)) for x in range(0, w, 4) for y in (1, h - 2)]
    borda += [img.getpixel((x, y)) for y in range(0, h, 4) for x in (1, w - 2)]
    return tuple(sorted(c[i] for c in borda)[len(borda) // 2] for i in range(3))


def quadrada(recorte: Image.Image, cobrir: bool = False) -> Image.Image:
    w, h = recorte.size
    if cobrir:
        # foto de ambiente: corta um quadrado, puxado para cima para não perder o rosto
        lado = min(w, h)
        x0 = (w - lado) // 2
        y0 = round((h - lado) * 0.25)
        return recorte.crop((x0, y0, x0 + lado, y0 + lado)).resize((LARGURA, LARGURA), Image.LANCZOS)
    lado = max(w, h)
    tela = Image.new("RGB", (lado, lado), FUNDO_ARTE)
    tela.paste(recorte, ((lado - w) // 2, (lado - h) // 2))
    final = tela.resize((LARGURA, LARGURA), Image.LANCZOS)
    return final.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))


def salvar(img: Image.Image, nome: str) -> None:
    img.save(DESTINO / f"{nome}.jpg", "JPEG", quality=88, optimize=True, progressive=True)
    print("ok", nome)


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    grade = Image.open(ORIGEM / GRADE).convert("RGB")
    for peca, (y0, y1) in LINHAS.items():
        for vista, (x0, x1) in COLUNAS.items():
            salvar(quadrada(grade.crop((x0, y0, x1, y1))), f"{peca}-{vista}")
        for vista, (x0, x1) in ETIQUETAS.items():
            salvar(quadrada(grade.crop((x0, y0 + 26, x1, y1 - 22))), f"{peca}-{vista}")

    apresentacao = Image.open(ORIGEM / APRESENTACAO).convert("RGB")
    for nome, caixa in RECORTES_APRESENTACAO.items():
        recorte = apresentacao.crop(caixa)
        if nome == "scheid-basic-mockup-frente":
            # o fim do logo da arte entra no canto do recorte
            recorte.paste(fundo(recorte), (0, 0, 50, 110))
            recorte.paste(fundo(recorte), (438, 60, recorte.width, 260))  # manga da camiseta de costas
        salvar(quadrada(recorte, cobrir="como-fica" in nome), nome)


if __name__ == "__main__":
    main()
