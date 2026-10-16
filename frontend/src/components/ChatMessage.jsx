/*
  ChatMessage.jsx

  Renders a single message in the chat conversation.
  Handles two roles:
  - 'user'      — the question the user typed (right-aligned, blue)
  - 'assistant' — the AI's answer (left-aligned, white card with sources)

  Props:
  - message: {
      role:    'user' | 'assistant'
      content: string          — the message text
      sources: array | null    — source passages (assistant only)
      grounded: boolean | null — whether the answer has evidence
      error:   boolean | null  — whether this is an error message
    }
*/

import { useState } from 'react'
import SourceCard from './SourceCard'

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user'
  // Controls whether the sources section is visible
  const [showSources, setShowSources] = useState(false)

  const hasSources = message.sources && message.sources.length > 0

  return (
    <div className={`flex w-full mb-4 ${isUser ? 'justify-end' : 'justify-start'}`}>

      {/* Avatar — only for assistant messages */}
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 mr-2 mt-1">
          <span className="text-white text-xs font-bold">AI</span>
        </div>
      )}

      {/* Message bubble */}
      <div className={`max-w-[80%] ${isUser ? 'max-w-[70%]' : 'w-full max-w-[85%]'}`}>

        {/* Bubble */}
        <div
          className={`
            rounded-2xl px-4 py-3 text-sm leading-relaxed
            ${isUser
              ? 'bg-blue-600 text-white rounded-tr-sm'
              : message.error
                ? 'bg-red-50 text-red-700 border border-red-200 rounded-tl-sm'
                : 'bg-white text-slate-800 border border-slate-200 shadow-sm rounded-tl-sm'
            }
          `}
        >
          {/* Message text — preserve newlines from the LLM response */}
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Sources section — only for assistant messages with sources */}
        {!isUser && hasSources && (
          <div className="mt-2 ml-0">
            {/* Toggle button */}
            <button
              onClick={() => setShowSources(!showSources)}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-blue-600 transition-colors mb-2 font-medium"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {showSources ? 'Hide' : 'Show'} {message.sources.length} source{message.sources.length !== 1 ? 's' : ''}
              <span className={`ml-1 transition-transform ${showSources ? 'rotate-180' : ''}`}>▾</span>
            </button>

            {/* Source cards */}
            {showSources && (
              <div className="flex flex-col gap-2">
                {message.sources.map((source, i) => (
                  <SourceCard key={i} source={source} index={i + 1} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Grounding indicator — tells user if answer is evidence-based */}
        {!isUser && !message.error && (
          <div className="mt-1.5 flex items-center gap-1">
            {message.grounded === true && (
              <span className="text-xs text-green-600 flex items-center gap-1">
                <span>✓</span> Relevant document passages retrieved
              </span>
            )}
            {message.grounded === false && (
              <span className="text-xs text-yellow-600 flex items-center gap-1">
                <span>⚠</span> Could not verify from retrieved passages
              </span>
            )}
          </div>
        )}
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0 ml-2 mt-1">
          <span className="text-slate-600 text-xs font-bold">You</span>
        </div>
      )}
    </div>
  )
}
