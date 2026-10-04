"""Deterministic, source-linked diligence checks. No network or model calls."""
import base64
import io
import re
import zipfile
import posixpath
from xml.etree import ElementTree as ET

MAX_FILE = 2 * 1024 * 1024
MAX_SLIDES = 60
MAX_TEXT = 120000
NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def xml(data):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('Unsupported XML declarations in presentation.')
    return ET.fromstring(data)


def extract(document):
    name = document['name']
    try:
        data = base64.b64decode(document['data'], validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid file encoding.') from exc
    if not data or len(data) > MAX_FILE:
        raise ValueError('Each deck must be between 1 byte and 2 MiB.')
    suffix = name.rsplit('.', 1)[-1].lower()
    texts = []
    if suffix == 'pdf' and data.startswith(b'%PDF-'):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ValueError('Password-protected PDFs are not supported. Export an unlocked copy.')
        if len(reader.pages) > MAX_SLIDES:
            raise ValueError('Maximum 60 slides per deck.')
        total = 0
        for page in reader.pages:
            text = page.extract_text() or ''
            total += len(text)
            if total > MAX_TEXT:
                raise ValueError('Deck contains too much text; split it into smaller decks.')
            texts.append(text)
    elif suffix == 'pptx' and zipfile.is_zipfile(io.BytesIO(data)):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 2000 or sum(e.file_size for e in entries) > 32 * 1024 * 1024:
                raise ValueError('Presentation exceeds safe expanded-size limits.')
            if len({e.filename for e in entries}) != len(entries):
                raise ValueError('Duplicate entries in presentation.')
            if any(e.flag_bits & 1 for e in entries):
                raise ValueError('Encrypted presentation is not supported.')
            presentation = xml(archive.read('ppt/presentation.xml'))
            relationships = xml(archive.read('ppt/_rels/presentation.xml.rels'))
            targets = {r.attrib['Id']: r.attrib['Target'] for r in relationships
                       if r.attrib.get('TargetMode') != 'External'}
            slide_ids = presentation.findall('p:sldIdLst/p:sldId', NS)
            if len(slide_ids) > MAX_SLIDES:
                raise ValueError('Maximum 60 slides per deck.')
            for slide in slide_ids:
                target = targets[slide.attrib['{' + NS['r'] + '}id']]
                path = posixpath.normpath('ppt/' + target) if not target.startswith('/') else target.lstrip('/')
                if not re.fullmatch(r'ppt/slides/slide\d+\.xml', path):
                    raise ValueError('Unsupported slide relationship.')
                root = xml(archive.read(path))
                texts.append('\n'.join(' '.join(t.text or '' for t in p.findall('.//a:t', NS))
                                       for p in root.findall('.//a:p', NS)))
    else:
        raise ValueError('Upload a valid PDF or PPTX. Other file types are not supported.')
    if sum(map(len, texts)) > MAX_TEXT:
        raise ValueError('Deck contains too much text; split it into smaller decks.')
    if not texts or sum(len(t.strip()) for t in texts) < 40:
        raise ValueError('Not enough readable text. Scanned/image-only decks need a text-enabled PDF or PPTX; OCR is not included.')
    return {'name': name, 'slides': [{'slide': i + 1, 'text': t.strip()} for i, t in enumerate(texts)]}


TOPICS = [
    ('Problem and customer', r'\b(problem|pain|customer|buyer|user)\b', 'Who has this problem, and what paid evidence demonstrates urgency?'),
    ('Revenue model', r'\b(pricing|business model|subscription|monetiz\w*|revenue model)\b', 'What does a customer pay, how often, and what does delivery cost?'),
    ('Traction and retention', r'\b(traction|retention|churn|ARR|MRR|paying customers|active users|pilot)\b', 'Separate paid revenue, pilots, bookings, active users, and projections; provide dated source records.'),
    ('Market sizing', r'\b(TAM|SAM|SOM|market size|addressable market)\b', 'Show a bottom-up reachable market: buyer count × annual spend, with sources and dates.'),
    ('Competition and differentiation', r'\b(competitor\w*|competition|alternative\w*|differentiat\w*|moat)\b', 'Compare direct competitors, substitutes, and doing nothing; provide evidence for differentiation.'),
    ('Team', r'\b(team|founder\w*|cofounder\w*|co-founder\w*)\b', 'Verify founder experience, full-time commitments, ownership, and missing critical roles.'),
    ('Funding and use of funds', r'\b(raising|fundrais\w*|use of funds|funding|investment ask|round)\b', 'What amount is being raised, on what terms, and which measurable milestones will it fund?'),
    ('Unit economics and runway', r'\b(CAC|LTV|gross margin|burn|runway|unit economics)\b', 'Request dated cash, net monthly burn, retention cohorts, and acquisition economics.'),
]
CLAIMS = [
    (r'\b(no competitors?|zero competition|no competition)\b', 'Competition dismissed', 'Ask for substitute products and existing customer workarounds. Absence of named rivals does not establish a moat.'),
    (r'\b(guaranteed returns?|risk[- ]free|100% accurac\w*)\b', 'Absolute performance claim', 'Request the underlying evaluation, population, failure cases, and legal basis; this claim has not been verified.'),
    (r'\b(patent pending|patented|FDA approved|SOC ?2 certified)\b', 'Credential or regulatory claim', 'Request the registration, scope, date, and independent verification. Mentioning a credential is not evidence it is valid.'),
]
NUMBER = re.compile(r'(?<!\w)(?:[$€£]\s*)?\d[\d,]*(?:\.\d+)?\s*(?:%|billion|million|thousand|[kmb]\b)?', re.I)


def shingles(text):
    words = re.findall(r'[a-z0-9]+', text.lower())
    return {' '.join(words[i:i + 8]) for i in range(max(0, len(words) - 7))}


def review(primary, references):
    slides = primary['slides']
    findings = []
    coverage = []
    metrics = []
    for label, pattern, question in TOPICS:
        matched = [s['slide'] for s in slides if re.search(pattern, s['text'], re.I)]
        coverage.append({'topic': label, 'slides': matched, 'status': 'mentioned' if matched else 'not_found', 'question': question})
        if not matched:
            findings.append({'priority': 'follow_up', 'title': label + ': not found in extracted text',
                             'slides': [], 'evidence': '', 'question': question})
    for slide in slides:
        for pattern, title, question in CLAIMS:
            match = re.search(pattern, slide['text'], re.I)
            if match:
                findings.append({'priority': 'review', 'title': title, 'slides': [slide['slide']],
                                 'evidence': slide['text'][max(0, match.start()-70):match.end()+100], 'question': question})
        for line in slide['text'].splitlines():
            if NUMBER.search(line) and len(metrics) < 80:
                metrics.append({'slide': slide['slide'], 'text': line[:400], 'status': 'unverified_deck_claim'})
    # Same metric may legitimately differ by period or projection: flag for reconciliation only.
    arr = []
    for slide in slides:
        for match in re.finditer(r'\b(ARR|MRR)\s*[:=]?\s*([$€£])\s*(\d[\d,]*(?:\.\d+)?)\s*(million|thousand|billion|[kmb]\b)?', slide['text'], re.I):
            factor = {'k': 1e3, 'thousand': 1e3, 'm': 1e6, 'million': 1e6, 'b': 1e9, 'billion': 1e9}.get((match[4] or '').lower(), 1)
            arr.append((match[1].upper(), match[2], float(match[3].replace(',', ''))*factor, slide['slide'], match[0]))
    for label in ('ARR', 'MRR'):
        values = [v for v in arr if v[0] == label]
        for currency in sorted({v[1] for v in values}):
            group = [v for v in values if v[1] == currency]
            if len({v[2] for v in group}) > 1:
                findings.append({'priority': 'review', 'title': f'{label} values need reconciliation',
                                 'slides': sorted({v[3] for v in group}), 'evidence': '; '.join(v[4] for v in group)[:500],
                                 'question': 'These figures differ. Are they from different dates, definitions, or forecasts? Request the dated revenue bridge; this is not proof of an error.'})
    overlaps = []
    for reference in references:
        indexed = [(s, shingles(s['text'])) for s in reference['slides']]
        for slide in slides:
            own = shingles(slide['text'])
            if len(own) < 5:
                continue
            for other, theirs in indexed:
                shared = own & theirs
                if len(shared) >= 5:
                    overlaps.append({'slide': slide['slide'], 'reference': reference['name'], 'reference_slide': other['slide'],
                                     'shared_phrases': len(shared), 'excerpt': sorted(shared, key=lambda x: (-len(x), x))[0],
                                     'interpretation': 'Shared wording in supplied decks. Templates, quotations, and common sources can explain overlap; this does not establish copying or IP infringement.'})
    overlaps.sort(key=lambda x: -x['shared_phrases'])
    return {'version': '1.0', 'method': 'Document checks and exact phrase comparison; no generative AI or web search.',
            'document': primary['name'], 'slide_count': len(slides),
            'readable_slides': sum(bool(s['text']) for s in slides),
            'warnings': ['Charts, images, speaker notes, and scanned text are not evaluated. Topic mentions do not establish quality or truth.',
                         'No external fact checking, market-wide competitor search, originality clearance, or investment recommendation is provided.',
                         'Files and results are processed transiently, not saved to your account. Download the review before leaving.'],
            'coverage': coverage, 'findings': findings, 'metrics': metrics, 'overlaps': overlaps[:30],
            'reference_count': len(references), 'slides': slides}


def run(payload):
    primary = extract(payload['deck'])
    references = [extract(d) for d in payload.get('references', [])]
    result = review(primary, references)
    result['warnings'].extend(f"Slide {s['slide']} has no extractable text." for s in primary['slides'] if not s['text'])
    return result
