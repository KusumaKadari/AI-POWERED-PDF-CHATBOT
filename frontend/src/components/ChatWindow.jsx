/*
  ChatWindow.jsx

  The main conversation area. It:
  - Renders all chat messages in order
  - Auto-scrolls to the latest message when a new one arrives
  - Shows a loading indicator while the AI is generating
  - Shows an empty state when no document is loaded
  - Shows a prompt to ask a question when a document is ready

  Props:
  - messages:   array of message objects
  - isLoading:  boolean — show loading dots
  - hasDocument: boolean — whether a PDF is currently loaded
*/

import { useEffect, useRef } from 'react'
import ChatMessage from './ChatMessage'
import LoadingIndicator from './LoadingIndicator'

export default function ChatWindow({ messages, isLoading, hasDocument }) {
  // useRef gives us a reference to the DOM element at the bottom of the list.
  // We use it to scroll there whenever messages change.
  const bottomRef = useRef(null)

  // Every time the messages array changes (new message added) or loading state
  // changes, scroll to the bottom so the user always sees the latest content.
  useEffect(() => {
    // scrollIntoView moves the browser's viewport to that element
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  return (
    // chat-scroll is our custom scrollbar class from index.css
    <div className="flex-1 overflow-y-auto p-4 chat-scroll">

      {/* ── Empty state: no document uploaded ── */}
      {!hasDocument && messages.length === 0 && (
        <div className="h-full flex flex-col items-center justify-center text-center px-8 py-16">
          <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-slate-700 mb-2">
            No document loaded
          </h3>
          <p className="text-slate-400 text-sm max-w-xs leading-relaxed">
            Upload a PDF in the sidebar to get started. Once processed, you can
            ask questions about it in natural language.
          </p>

          {/* Example questions to inspire users */}
          <div className="mt-6 space-y-2 w-full max-w-sm">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
              Example questions you can ask
            </p>
            {[
              'What are the main findings of this document?',
              'Summarize chapter 2 in simple terms.',
              'What does the author say about X?',
              'On which page is Y mentioned?',
            ].map((q, i) => (
              <div key={i} className="text-left px-3 py-2 bg-slate-50 rounded-lg border border-slate-200">
                <p className="text-sm text-slate-500 italic">"{q}"</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Ready state: document loaded, no questions yet ── */}
      {hasDocument && messages.length === 0 && (
        <div className="h-full flex flex-col items-center justify-center text-center px-8 py-16">
          <div className="w-16 h-16 rounded-2xl bg-green-50 flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-slate-700 mb-2">
            Document ready
          </h3>
          <p className="text-slate-400 text-sm max-w-xs">
            Your PDF has been processed. Ask any question about it below.
          </p>
        </div>
      )}

      {/* ── Message list ── */}
      {messages.length > 0 && (
        <div className="space-y-1">
          {messages.map((message, index) => (
            <ChatMessage key={index} message={message} />
          ))}
        </div>
      )}

      {/* ── Loading indicator ── */}
      {isLoading && (
        <div className="flex justify-start mb-4 mt-2">
          {/* Assistant avatar */}
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 mr-2 mt-1">
            <span className="text-white text-xs font-bold">AI</span>
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
            <LoadingIndicator message="Searching document..." />
          </div>
        </div>
      )}

      {/* Invisible element at the bottom — we scroll to this */}
      <div ref={bottomRef} />
    </div>
  )
}
