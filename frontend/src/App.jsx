/*
  App.jsx — Root Application Component

  This is the top-level component that:
  1. Holds all application state (document, messages, loading flags)
  2. Defines all event handlers (upload, ask question, remove document)
  3. Composes the layout: Sidebar + Chat area

  Why keep state here instead of in individual components?
  Because multiple components need to share the same data:
  - Sidebar needs to know about the document
  - ChatWindow needs the messages
  - The question input needs to know if a document is loaded
  Lifting state to the common parent (App) is the standard React pattern.
*/

import { useState, useRef } from 'react'
import Sidebar from './components/Sidebar'
import ChatWindow from './components/ChatWindow'
import { uploadDocument, deleteDocument, askQuestion, summarizeDocument } from './services/api'

export default function App() {

  // ── State ────────────────────────────────────────────────────

  // The currently loaded document (null when no document is loaded)
  // Shape: { document_id, filename, page_count, chunk_count, status }
  const [document, setDocument] = useState(null)

  // All chat messages for this session
  // Each message: { role: 'user'|'assistant', content, sources, grounded, error }
  const [messages, setMessages] = useState([])

  // The text currently typed in the question input
  const [question, setQuestion] = useState('')

  // Loading states for different operations
  const [isUploading, setIsUploading] = useState(false)
  const [isAsking, setIsAsking] = useState(false)
  const [isSummarizing, setIsSummarizing] = useState(false)

  // Error from upload (shown in sidebar)
  const [uploadError, setUploadError] = useState(null)

  // Ref to the textarea — used to focus it after sending a message
  const questionInputRef = useRef(null)

  // ── Helpers ──────────────────────────────────────────────────

  // Append a message to the chat history
  const addMessage = (role, content, extras = {}) => {
    setMessages(prev => [...prev, { role, content, ...extras }])
  }

  // ── Event Handlers ───────────────────────────────────────────

  /**
   * Called by FileUploader when a valid PDF file is selected.
   * Uploads the file to the backend and stores the result.
   */
  const handleUpload = async (file) => {
    if (!file) {
      // Called with null when user clicks "Try again" on an error
      setUploadError(null)
      return
    }

    setIsUploading(true)
    setUploadError(null)

    try {
      const result = await uploadDocument(file)
      setDocument(result)
      // Clear previous conversation when a new document is loaded
      setMessages([])
    } catch (err) {
      setUploadError(err.message || 'Failed to process the document. Please try again.')
    } finally {
      // Always stop the loading spinner, whether we succeeded or failed
      setIsUploading(false)
    }
  }

  /**
   * Called when the user clicks "Remove Document".
   * Deletes the document from the backend and resets local state.
   */
  const handleRemove = async () => {
    if (!document) return

    try {
      await deleteDocument(document.document_id)
    } catch (err) {
      setUploadError(`Could not remove the document: ${err.message}`)
      return
    }

    setDocument(null)
    setMessages([])
    setQuestion('')
    setUploadError(null)
  }

  /**
   * Called when the user submits a question.
   * Sends the question to the backend and adds the answer to the chat.
   */
  const handleAsk = async (e) => {
    e.preventDefault() // prevent page reload on form submit

    const trimmedQuestion = question.trim()
    if (!trimmedQuestion || isAsking || !document) return

    // Add the user's message immediately so the UI feels responsive
    addMessage('user', trimmedQuestion)
    setQuestion('')
    setIsAsking(true)

    try {
      const result = await askQuestion(document.document_id, trimmedQuestion)

      addMessage('assistant', result.answer, {
        sources: result.sources || [],
        grounded: result.grounded,
      })
    } catch (err) {
      addMessage('assistant', `Sorry, I couldn't get an answer: ${err.message}`, {
        error: true,
      })
    } finally {
      setIsAsking(false)
      // Return focus to the input so the user can type the next question
      setTimeout(() => questionInputRef.current?.focus(), 100)
    }
  }

  /**
   * Called when user presses Enter in the textarea (without Shift).
   * Shift+Enter inserts a newline instead of submitting.
   */
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleAsk(e)
    }
  }

  /**
   * Generates a document summary and adds it to the chat.
   */
  const handleSummarize = async () => {
    if (!document || isSummarizing) return

    setIsSummarizing(true)
    addMessage('user', '📋 Generate a summary of this document')

    try {
      const result = await summarizeDocument(document.document_id)
      addMessage('assistant', result.summary, {
        sources: result.sources || [],
        grounded: true,
      })
    } catch (err) {
      addMessage('assistant', `Could not generate summary: ${err.message}`, {
        error: true,
      })
    } finally {
      setIsSummarizing(false)
    }
  }

  // ── Render ───────────────────────────────────────────────────

  return (
    // Full-height flex layout: sidebar on left, main content on right
    <div className="flex h-screen bg-slate-100 overflow-hidden">

      {/* Left sidebar */}
      <Sidebar
        document={document}
        onUpload={handleUpload}
        onRemove={handleRemove}
        onSummarize={handleSummarize}
        isUploading={isUploading}
        uploadError={uploadError}
        isSummarizing={isSummarizing}
      />

      {/* Right main area: chat window + input */}
      <main className="flex-1 flex flex-col min-w-0 bg-slate-50">

        {/* Top bar */}
        <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between flex-shrink-0">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">
              {document ? document.filename : 'No document loaded'}
            </h2>
            <p className="text-xs text-slate-400">
              {document
                ? `${document.page_count} pages · ${document.chunk_count} searchable chunks`
                : 'Upload a PDF to start asking questions'
              }
            </p>
          </div>

          {/* Clear conversation button */}
          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
            >
              Clear chat
            </button>
          )}
        </header>

        {/* Chat messages area */}
        <ChatWindow
          messages={messages}
          isLoading={isAsking}
          hasDocument={!!document}
        />

        {/* Question input bar */}
        <div className="bg-white border-t border-slate-200 p-4 flex-shrink-0">
          <form onSubmit={handleAsk} className="flex gap-3 items-end">

            {/* Textarea instead of input so users can write multi-line questions */}
            <textarea
              ref={questionInputRef}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                document
                  ? 'Ask a question about your document... (Enter to send, Shift+Enter for newline)'
                  : 'Upload a PDF first to ask questions'
              }
              disabled={!document || isAsking}
              rows={1}
              className="
                flex-1 resize-none rounded-xl border border-slate-200 bg-slate-50
                px-4 py-3 text-sm text-slate-800 placeholder-slate-400
                focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                disabled:opacity-50 disabled:cursor-not-allowed
                transition-all
              "
              // Auto-grow the textarea as user types (up to 5 lines)
              style={{ maxHeight: '120px' }}
              onInput={(e) => {
                e.target.style.height = 'auto'
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
              }}
            />

            {/* Send button */}
            <button
              type="submit"
              disabled={!document || isAsking || !question.trim()}
              className="
                flex-shrink-0 w-10 h-10 rounded-xl bg-blue-600 text-white
                flex items-center justify-center
                hover:bg-blue-700 active:bg-blue-800
                disabled:opacity-40 disabled:cursor-not-allowed
                transition-colors
              "
              aria-label="Send question"
            >
              {isAsking ? (
                // Small spinner on the button while loading
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              )}
            </button>
          </form>

          {/* Disclaimer */}
          <p className="text-xs text-slate-400 mt-2 text-center">
            Answers use retrieved passages from your PDF. Check sources for important details.
          </p>
        </div>
      </main>
    </div>
  )
}
