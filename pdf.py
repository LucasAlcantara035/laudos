"""PDF do laudo (A4). O sistema NUNCA assina: a última página traz apenas o bloco em branco do engenheiro."""
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (HRFlowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)
import checklists as C, validacao as V

AZUL = colors.HexColor("#0b4f6c")
_ss = getSampleStyleSheet()
TXT = ParagraphStyle("t", parent=_ss["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13)
NEG = ParagraphStyle("n", parent=TXT, fontName="Helvetica-Bold")
RED = ParagraphStyle("r", parent=TXT, fontName="Helvetica-Bold", textColor=colors.HexColor("#b3261e"))
TIT = ParagraphStyle("tit", parent=TXT, fontName="Helvetica-Bold", fontSize=15, leading=19, spaceAfter=4)
SEC = ParagraphStyle("s", parent=TXT, fontName="Helvetica-Bold", fontSize=10.5, textColor=colors.white,
                     backColor=AZUL, borderPadding=(3, 4, 3, 4), spaceBefore=12, spaceAfter=7)
CEN = ParagraphStyle("c", parent=TXT, alignment=1)


def _s(t):
    """Texto seguro para a fonte Helvetica (sem ômega)."""
    return escape(str(t if t not in (None, "") else "-")).replace("MΩ", " megaohm").replace("Ω", " ohm").replace("\n", "<br/>")


def P(t, st=TXT):
    return Paragraph(_s(t), st)


def gerar_pdf(d, fotos, laudo_id):
    buf, agora = BytesIO(), datetime.now().strftime("%d/%m/%Y %H:%M")

    def rodape(c, doc):
        c.saveState()
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.grey)
        c.drawString(2 * cm, 1.1 * cm, f"Laudo {laudo_id[:8]} · gerado em {agora}")
        c.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Página {doc.page}")
        c.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                            bottomMargin=2 * cm, title=C.TITULOS[d["tipo"]])
    L = d.get("laudo") or {}
    data_br = "/".join(reversed(str(d["data"]).split("-")))
    f = [P(C.TITULOS[d["tipo"]], TIT), P(f"{C.TIPOS[d['tipo']]} · Finalidade: {d['finalidade']}"), Spacer(1, 4)]

    f.append(P("1. Identificação", SEC))
    for k, v in [("Cliente", d["cliente"]), ("CPF/CNPJ", d["doc"]), ("Local", d["local"]), ("Data da inspeção", data_br)]:
        f.append(P(f"{k}: {v or '-'}"))
    f.append(P("2. Normas de referência", SEC)); f.append(P(C.normas(d)))
    f.append(P("3. Características da instalação", SEC))
    for k, v in [("Tensão nominal", d["tensao"]), ("Potência/demanda", d["potencia"]), ("Esquema de aterramento", d["esquema"]),
                 (C.LB[d["tipo"]][0], d["quadros"]), ("Descrição", d["desc"])]:
        f.append(P(f"{k}: {v or '-'}"))

    f.append(P("4. Checklist de inspeção", SEC))
    nome = {"C": "Conforme", "NC": "NÃO CONFORME", "NA": "N/A"}
    for g in C.grupos(d):
        f.append(P(C.CK[g]["t"], NEG))
        rows = []
        for k, t in C.CK[g]["l"]:
            v = d.get("ck", {}).get(k, {})
            st = RED if v.get("s") == "NC" else TXT
            rows.append([P(t), P(nome.get(v.get("s"), "Não avaliado"), st), P(v.get("o", ""))])
        tb = Table(rows, colWidths=[8.4 * cm, 2.8 * cm, 5.8 * cm], repeatRows=0)
        tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .4, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        f += [tb, Spacer(1, 6)]

    f.append(P("5. Medições e ensaios", SEC))
    eletrico = d["tipo"] in ("bt", "mt")
    if eletrico or d["res"]:
        f.append(P(f"Resistência de aterramento: {d['res'] + ' Ω' if d['res'] else 'não medida'}"))
    if eletrico or d["iso"]:
        f.append(P(f"Isolação mínima: {d['iso'] + ' MΩ' if d['iso'] else 'não medida'}"))
    f.append(P(f"{C.LB[d['tipo']][1].replace(' (resultado)', '')}: {d['cont'] or 'não informado'}"))
    if d["obs"]:
        f.append(P("Observações: " + d["obs"]))

    f.append(P("6. Não conformidades", SEC))
    nc = V.nao_conformidades(d)
    if nc:
        for i, x in enumerate(nc, 1):
            f.append(P(f"{i}. [{x['norma']}] {x['item']}" + (f" ({x['obs']})" if x["obs"] else "")))
    else:
        f.append(P("Nenhuma não conformidade registrada."))

    for n, tit, chave in [(7, "Análise técnica", "analise"), (8, "Recomendações", "recs"), (9, "Conclusão", "conclusao")]:
        f.append(P(f"{n}. {tit}", SEC)); f.append(P(L.get(chave) or "Texto não gerado."))

    if fotos:
        f.append(P("10. Registro fotográfico", SEC))
        for i, ft in enumerate(fotos, 1):
            try:
                w, h = ImageReader(BytesIO(ft["imagem"])).getSize()
                esc = min(12 * cm / w, 8 * cm / h)
                f.append(KeepTogether([Image(BytesIO(ft["imagem"]), w * esc, h * esc),
                                       P(f"Foto {i}: {ft['item'] or ''} {ft['legenda'] or ''}"), Spacer(1, 6)]))
            except Exception:
                f.append(P(f"Foto {i}: arquivo de imagem inválido."))

    f.append(KeepTogether([Spacer(1, 2.2 * cm), HRFlowable(width="55%", thickness=.6, color=colors.black, hAlign="CENTER"),
                           Spacer(1, 4), P(d["resp"] or "Engenheiro responsável", ParagraphStyle("b", parent=CEN, fontName="Helvetica-Bold")),
                           P(f"CREA: {d['crea'] or '________'}   ART: {d['art'] or '________'}", CEN),
                           P("Assinatura do engenheiro responsável", CEN)]))
    doc.build(f, onFirstPage=rodape, onLaterPages=rodape)
    return buf.getvalue()
