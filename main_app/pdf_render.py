"""PDF generation for signed documents.

Pure-Python via ReportLab — no native deps, no Heroku buildpacks needed.
Renders the document body + every signature into a clean letter-size PDF.
"""
from io import BytesIO

from reportlab.lib.colors import HexColor, grey
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    HRFlowable,
    KeepTogether,
)


def _styles():
    """Build a small style sheet — kept inline so callers don't accidentally
    mutate ReportLab's global stylesheet."""
    base = getSampleStyleSheet()
    s = {
        'title': ParagraphStyle(
            'doc-title', parent=base['Title'],
            fontName='Helvetica-Bold', fontSize=18, leading=22,
            spaceAfter=12, textColor=HexColor('#102026'),
        ),
        'meta': ParagraphStyle(
            'doc-meta', parent=base['Normal'],
            fontName='Helvetica', fontSize=9, leading=12,
            textColor=grey, spaceAfter=18,
        ),
        'body': ParagraphStyle(
            'doc-body', parent=base['Normal'],
            fontName='Helvetica', fontSize=10.5, leading=16,
            spaceAfter=10, textColor=HexColor('#102026'),
        ),
        'section': ParagraphStyle(
            'doc-section', parent=base['Heading2'],
            fontName='Helvetica-Bold', fontSize=13, leading=18,
            spaceBefore=14, spaceAfter=8, textColor=HexColor('#1B4D5A'),
        ),
        'sig-label': ParagraphStyle(
            'sig-label', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=10, leading=14,
            textColor=HexColor('#1B4D5A'),
            spaceBefore=10, spaceAfter=4,
        ),
        'sig-name': ParagraphStyle(
            'sig-name', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=11, leading=15,
            textColor=HexColor('#102026'),
        ),
        'sig-cursive': ParagraphStyle(
            'sig-cursive', parent=base['Normal'],
            fontName='Helvetica-Oblique', fontSize=22, leading=28,
            textColor=HexColor('#1B3550'),
            spaceBefore=4, spaceAfter=4,
        ),
        'sig-meta': ParagraphStyle(
            'sig-meta', parent=base['Normal'],
            fontName='Helvetica', fontSize=8.5, leading=12,
            textColor=grey, spaceAfter=14,
        ),
    }
    return s


def _esc(text):
    """Minimal escaping for Paragraph — ReportLab uses an XML-ish mini-language."""
    return (text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def render_document_pdf(document):
    """Return a bytes blob containing a PDF of the document + all signatures."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
        title=document.title,
        author=document.owner.username,
    )
    st = _styles()
    story = []

    # Header
    story.append(Paragraph(_esc(document.title), st['title']))
    meta_bits = [
        f'Owner: {_esc(document.owner.username)}',
        f'Created: {document.created_at.strftime("%B %-d, %Y")}',
        f'Document ID: {document.id}',
        f'Status: {document.get_status_display()}',
    ]
    story.append(Paragraph(' &nbsp;·&nbsp; '.join(meta_bits), st['meta']))
    story.append(HRFlowable(width='100%', thickness=0.5, color=HexColor('#D8DEE6')))
    story.append(Spacer(1, 0.18 * inch))

    # Body — split on blank lines so each paragraph is its own flowable
    raw_paragraphs = [p.strip() for p in document.body.split('\n\n')]
    for para in raw_paragraphs:
        if not para:
            continue
        # Preserve line breaks within a paragraph
        html = _esc(para).replace('\n', '<br/>')
        story.append(Paragraph(html, st['body']))

    # Signatures section — auto-populated for both parties.
    # Disclosing Party = the document owner (uses disclosing_party_name if set,
    # else the owner's account email/username), signed when the document was
    # created. Receiving Party = whoever signed via the public sign URL.
    signatures = list(document.signatures.all())
    story.append(Spacer(1, 0.25 * inch))
    story.append(HRFlowable(width='100%', thickness=0.5, color=HexColor('#D8DEE6')))
    story.append(Paragraph('Signatures', st['section']))

    # ----- Disclosing Party -----
    disclosing_name = (document.disclosing_party_name or '').strip() \
        or (document.owner.get_full_name() or '').strip() \
        or document.owner.email \
        or document.owner.username
    disclosing_date = document.created_at.strftime('%B %-d, %Y')
    disclosing_block = [
        Paragraph('DISCLOSING PARTY', st['sig-label']),
        Paragraph(_esc(disclosing_name), st['sig-name']),
        Paragraph(_esc(disclosing_name), st['sig-cursive']),
        Paragraph(f'Date signed: {disclosing_date}', st['sig-meta']),
    ]
    story.append(KeepTogether(disclosing_block))
    story.append(Spacer(1, 0.18 * inch))

    # ----- Receiving Party (one block per signer) -----
    if signatures:
        for i, sig in enumerate(signatures):
            label = 'RECEIVING PARTY' if len(signatures) == 1 else f'RECEIVING PARTY {i + 1}'
            meta_lines = [f'Date signed: {sig.signed_at.strftime("%B %-d, %Y at %I:%M %p")} (UTC)']
            if sig.signer_email:
                meta_lines.append(_esc(sig.signer_email))
            if sig.ip_address:
                meta_lines.append(f'IP {sig.ip_address}')
            block = [
                Paragraph(label, st['sig-label']),
                Paragraph(_esc(sig.signer_name), st['sig-name']),
                Paragraph(_esc(sig.typed_signature), st['sig-cursive']),
                Paragraph(' &nbsp;·&nbsp; '.join(meta_lines), st['sig-meta']),
            ]
            story.append(KeepTogether(block))
            if i < len(signatures) - 1:
                story.append(Spacer(1, 0.12 * inch))
    else:
        block = [
            Paragraph('RECEIVING PARTY', st['sig-label']),
            Paragraph(
                '<i>Not yet signed. This document will be countersigned by the '
                'Receiving Party via the InFlow signing link.</i>',
                st['sig-meta'],
            ),
        ]
        story.append(KeepTogether(block))

    doc.build(story)
    return buf.getvalue()
