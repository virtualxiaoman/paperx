from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen.canvas import Canvas

SAMPLE_LICENSE = "CC0-1.0; original synthetic content, no extracted paper content."


def generate(out: Path):
    """Deterministic, original fixtures. No paper content is redistributed."""
    out.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    def canvas(name):
        c = Canvas(str(out / name), pagesize=(612, 792), invariant=1)
        c.setTitle("Paperx synthetic fixture")
        c.setAuthor("Paperx fixture generator")
        return c

    def line(c, x, y, text, bold=False):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 12 if bold else 10)
        c.drawString(x, y, text)

    c = canvas("single-column.pdf")
    line(c, 54, 740, "Abstract", True)
    line(c, 54, 718, "SINGLE_START A small original test paper about reading.")
    line(c, 54, 680, "1 Introduction", True)
    line(c, 54, 658, "Paragraph alpha has a known location on page one.")
    line(c, 54, 644, "This visual line continues the same paragraph.")
    line(c, 54, 600, "Paragraph beta is separated by a visible gap.")
    c.showPage()
    line(c, 54, 740, "2 Conclusion", True)
    line(c, 54, 718, "SINGLE_END Page two completes this synthetic example.")
    c.save()

    c = canvas("multi-column.pdf")
    line(c, 54, 740, "1 Introduction", True)
    for x, label in [(54, "LEFT"), (330, "RIGHT")]:
        for i in range(8):
            line(c, x, 710 - i * 16, f"{label}_{i + 1} original text in column.")
    c.save()

    c = canvas("formula-dense.pdf")
    line(c, 54, 740, "1 Equations", True)
    for i, text in enumerate(["x = a + b (1)", "y = x * x (2)", "z = x / y (3)"]):
        line(c, 140, 685 - i * 65, text)
    c.save()

    c = canvas("figure-table.pdf")
    line(c, 54, 740, "1 Results", True)
    c.rect(60, 450, 225, 210)
    for i, h in enumerate([45, 90, 135]):
        c.setFillColorRGB(0.1, 0.35 + i * 0.1, 0.6)
        c.rect(88 + i * 58, 470, 32, h, fill=1)
    c.setFillColorRGB(0, 0, 0)
    line(c, 54, 426, "Figure 1: Original synthetic bar chart.")
    for y in [350, 320, 290, 260]:
        c.line(60, y, 400, y)
    for x in [60, 230, 400]:
        c.line(x, 260, x, 350)
    for y, text in [(331, "Metric"), (301, "Alpha"), (271, "Beta")]:
        line(c, 72, y, text)
    line(c, 248, 331, "Value")
    line(c, 248, 301, "10")
    line(c, 248, 271, "20")
    c.save()

    c = canvas("scan-like.pdf")
    image = Image.new("RGB", (1000, 1300), "white")
    draw = ImageDraw.Draw(image)
    draw.text((80, 100), "Synthetic scanned page - NO TEXT LAYER", fill="black", font_size=30)
    draw.text((80, 175), "OCR is deliberately unavailable in stage 0.", fill="black", font_size=26)
    c.drawImage(ImageReader(image), 0, 0, width=612, height=792)
    c.save()

    for name, chinese in [("paired-en.pdf", False), ("paired-zh.pdf", True)]:
        c = canvas(name)
        if chinese:
            c.setFont("STSong-Light", 18)
            c.drawString(54, 740, "合成测试文档")
            c.setFont("STSong-Light", 12)
            c.drawString(54, 700, "这是一段人工编写的中文配对样本，不是 AI 翻译。")
            c.drawString(54, 676, "同一个实验可以有不同的排版长度。")
        else:
            line(c, 54, 740, "1 Paired Sample", True)
            line(c, 54, 700, "This is an original, manually authored bilingual fixture.")
            line(c, 54, 676, "The same experiment can have different layout lengths.")
        c.save()
    # Additional geometry probe: same source page repeated with each PDF rotation.
    writer = PdfWriter()
    for angle in (0, 90, 180, 270):
        page = PdfReader(out / "single-column.pdf").pages[0]
        page.rotate(angle)
        writer.add_page(page)
    with (out / "rotated.pdf").open("wb") as stream:
        writer.write(stream)


if __name__ == "__main__":
    generate(Path(__file__).resolve().parents[1] / "tests/fixtures")
