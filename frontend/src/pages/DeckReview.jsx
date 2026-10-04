import { useState } from 'react'
import { apiRequest } from '../api/client'
import PageHeader from '../components/common/PageHeader'
import ErrorNotice from '../components/common/ErrorNotice'
import '../styles/decks.css'

const LIMIT = 2 * 1024 * 1024
function encodedFile(file) {
  if (!/\.(pdf|pptx)$/i.test(file.name) || file.size > LIMIT || !file.size) throw new Error('Choose a PDF or PPTX up to 2 MiB per file.')
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Could not read the selected file.'))
    reader.onload = () => resolve({ name: file.name, data: reader.result.split(',')[1] })
    reader.readAsDataURL(file)
  })
}
export default function DeckReview() {
  const [deck, setDeck] = useState(null)
  const [references, setReferences] = useState([])
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all')
  async function submit(e) {
    e.preventDefault(); setError(''); setResult(null); setBusy(true)
    try {
      if (references.length > 2) throw new Error('Choose at most two comparison decks.')
      const payload = { deck: await encodedFile(deck), references: await Promise.all(references.map(encodedFile)) }
      setResult(await apiRequest('/api/decks/review', { method: 'POST', body: JSON.stringify(payload), signal: AbortSignal.timeout(90000) }))
      setFilter('all')
    } catch (e) { setError(e.name === 'TimeoutError' ? 'The service took too long to respond. It may be waking from free-tier sleep; try again.' : e.message) }
    finally { setBusy(false) }
  }
  function download() {
    const lines = ['# Perscipil · Deck diligence', result.document, '', result.method, '', ...result.warnings, '', '## Review questions',
      ...result.findings.map(f => `\n### ${f.title}\nSlides: ${f.slides.join(', ') || 'Not found'}\n${f.evidence}\n${f.question}`),
      '\n## Topic coverage', ...result.coverage.map(c => `${c.topic}: ${c.status}; slides ${c.slides.join(', ') || '—'}. ${c.question}`),
      '\n## Deck-reported numbers (unverified)', ...result.metrics.map(m => `Slide ${m.slide}: ${m.text}`),
      '\n## Wording overlap', ...result.overlaps.map(o => `Slide ${o.slide} / ${o.reference}, slide ${o.reference_slide}: “${o.excerpt}”. ${o.interpretation}`)]
    const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' }))
    const a = document.createElement('a'); a.href = url; a.download = 'Perscipil_Deck_Review.txt'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const visible = result?.findings.filter(f => filter === 'all' || f.priority === filter) || []
  return <div className="page-stack deck-review">
    <PageHeader eyebrow="VC research desk" title="Deck diligence">Turn a startup pitch into a source-linked diligence checklist. Inspect the claims, find gaps, and compare wording.</PageHeader>
    <form className="panel deck-upload" onSubmit={submit}>
      <div><span className="eyebrow">01 / THE PITCH</span><h2>Start with the deck.</h2><p>PDF or PPTX · 2 MiB per file · up to 60 slides. Use text-enabled files; scanned images and charts aren’t read.</p>
        <label className="form-stack">Startup pitch deck<input required disabled={busy} type="file" accept=".pdf,.pptx" onChange={e => { setDeck(e.target.files[0] || null); setResult(null) }} /></label>
      </div>
      <div><span className="eyebrow">02 / THE COMPARISON</span><h2>Bring reference decks.</h2><p>Optional: add up to two decks you have permission to use. Comparison checks shared wording, not market-wide originality.</p>
        <label className="form-stack">Reference decks<input disabled={busy} multiple type="file" accept=".pdf,.pptx" onChange={e => { setReferences(Array.from(e.target.files)); setResult(null) }} /></label>
      </div>
      <div className="deck-upload-footer"><p>Processed transiently by Perscipil. No third-party AI calls, no account storage. Download results before leaving.</p><button className="btn btn-primary" disabled={busy || !deck}>{busy ? 'Reviewing deck…' : 'Review pitch deck'}</button></div>
    </form>
    <ErrorNotice message={error} />
    <p role="status" aria-live="polite">{busy ? 'Extracting slide text and running diligence checks. Free hosting may take a moment to wake up.' : result ? `Review ready: ${result.slide_count} slides, ${result.findings.length} questions.` : 'Document checks are available at no additional API cost.'}</p>
    {result && <>
      <section className="panel"><div className="deck-result-heading"><div><span className="eyebrow">REVIEW BRIEF</span><h2>{result.document}</h2></div><button className="btn btn-ghost" onClick={download}>Download diligence memo</button></div>
        <div className="deck-stats"><div><strong>{result.readable_slides}/{result.slide_count}</strong><span>Slides with readable text</span></div><div><strong>{result.findings.length}</strong><span>Questions to investigate</span></div><div><strong>{result.metrics.length}</strong><span>Number excerpts · up to 80</span></div><div><strong>{result.overlaps.length}</strong><span>Wording matches · up to 30</span></div></div>
        <p>{result.method}</p>{result.warnings.map(w => <p className="deck-note" key={w}>{w}</p>)}
      </section>
      <section className="panel"><div className="deck-result-heading"><h2>What needs a closer look</h2><label>Show <select value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All questions</option><option value="review">Claims to review</option><option value="follow_up">Missing topics</option></select></label></div>
        {visible.length ? <div className="deck-findings">{visible.map((f, i) => <article className="deck-finding" key={`${f.title}-${i}`}><span className="eyebrow">{f.priority === 'review' ? 'VERIFY THE CLAIM' : 'REQUEST INFORMATION'} · {f.slides.length ? `SLIDE ${f.slides.join(', ')}` : 'NOT FOUND IN TEXT'}</span><h3>{f.title}</h3>{f.evidence && <blockquote>{f.evidence}</blockquote>}<p>{f.question}</p></article>)}</div> : <p>No findings in this view. This does not mean the deck is complete or verified.</p>}
      </section>
      <section className="panel"><h2>Investment story coverage</h2><p>“Mentioned” means matching language appeared, not that the topic is adequately supported.</p><div className="deck-coverage">{result.coverage.map(c => <article key={c.topic}><h3>{c.topic}</h3><span>{c.slides.length ? `Mentioned · slides ${c.slides.join(', ')}` : 'Not found in text'}</span><p>{c.question}</p></article>)}</div></section>
      <section className="panel"><h2>Potential wording overlap</h2>{!result.reference_count ? <p>Add reference decks to compare. No comparison was performed.</p> : result.overlaps.length ? result.overlaps.map((o, i) => <article className="deck-finding" key={i}><h3>Slide {o.slide} ↔ {o.reference}, slide {o.reference_slide}</h3><blockquote>{o.excerpt}</blockquote><p>{o.shared_phrases} shared eight-word phrases. {o.interpretation}</p></article>) : <p>No substantial exact phrase overlap found in the supplied decks. Paraphrasing, visual similarities, and other companies have not been checked.</p>}</section>
      <section className="panel"><h2>Numbers worth checking</h2><p>Deck-reported excerpts; forecasts and actuals are not automatically distinguished. Check dates, units, definitions, and source records.</p>{result.metrics.length ? result.metrics.map((m, i) => <div className="deck-number" key={i}><span>Slide {m.slide}</span><p>{m.text}</p></div>) : <p>No numeric excerpts extracted.</p>}</section>
      <section className="panel"><h2>Slide evidence</h2><p>Check extraction against the original deck before relying on a finding.</p>{result.slides.map(s => <details key={s.slide}><summary>Slide {s.slide}{!s.text && ' · no readable text'}</summary><pre>{s.text || 'No extractable text. Review this slide manually.'}</pre></details>)}</section>
    </>}
  </div>
}
