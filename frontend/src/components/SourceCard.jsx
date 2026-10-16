/*
  SourceCard.jsx

  Displays a single retrieved source passage from the PDF.

  This is important for RAG applications — users need to be able to
  verify that the AI's answer is actually supported by the document.
  Without source citations, you can't tell if the model is hallucinating.

  Props:
  - source: {
      page:  number  — original PDF page number
      text:  string  — the retrieved passage text
      score: number  — similarity score (0.0 to 1.0)
    }
  - index: number — which source this is (1, 2, 3...)
*/

import { useState } from 'react'

export default function SourceCard({ source, index }) {
  // Controls whether the full passage text is visible or collapsed
  const [expanded, setExpanded] = useState(false)

  // Convert the 0–1 score into a human-readable label and color
  // These thresholds are approximate — adjust as you evaluate quality
  const getScoreLabel = (score) => {
    if (score >= 0.7) return { label: 'High relevance', color: 'text-green-600 bg-green-50' }
    if (score >= 0.5) return { label: 'Medium relevance', color: 'text-yellow-600 bg-yellow-50' }
    return { label: 'Low relevance', color: 'text-slate-500 bg-slate-100' }
  }

  const scoreInfo = getScoreLabel(source.score)

  // Show a preview (first 150 characters) when collapsed
  const preview = source.text.length > 150
    ? source.text.slice(0, 150) + '...'
    : source.text

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden text-sm">
      {/* Header row — page number, score badge, expand button */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border-b border-slate-200">
        <div className="flex items-center gap-2">
          {/* Source number */}
          <span className="text-xs font-semibold text-slate-400">
            SOURCE {index}
          </span>

          {/* Page number badge — this comes from the PDF metadata, not the LLM */}
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-medium">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Page {source.page}
          </span>

          {/* Relevance score badge */}
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${scoreInfo.color}`}>
            {scoreInfo.label} ({Math.round(source.score * 100)}%)
          </span>
        </div>

        {/* Expand / collapse toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-blue-600 hover:text-blue-800 font-medium transition-colors"
          aria-expanded={expanded}
          aria-label={expanded ? 'Collapse source' : 'Expand source'}
        >
          {expanded ? 'Show less ↑' : 'Show more ↓'}
        </button>
      </div>

      {/* Passage text */}
      <div className="px-3 py-2 bg-white">
        <p className="text-slate-600 leading-relaxed">
          {/* Show preview or full text depending on expanded state */}
          {expanded ? source.text : preview}
        </p>
      </div>
    </div>
  )
}
