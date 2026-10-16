/*
  Sidebar.jsx

  The left panel of the application. Handles:
  - App branding/logo
  - PDF upload (delegates to FileUploader)
  - Document status display (uploading, processing, ready, error)
  - Summary generation button
  - Document removal / reset

  Props:
  - document:       object | null  — currently loaded document info
  - onUpload:       (file) => void — called when a file is selected
  - onRemove:       () => void     — called when user clicks "Remove document"
  - onSummarize:    () => void     — called when user requests a summary
  - isUploading:    boolean        — upload + processing in progress
  - uploadError:    string | null  — error from last upload attempt
  - isSummarizing:  boolean        — summary is being generated
*/

import FileUploader from './FileUploader'
import LoadingIndicator from './LoadingIndicator'

export default function Sidebar({
  document,
  onUpload,
  onRemove,
  onSummarize,
  isUploading,
  uploadError,
  isSummarizing,
}) {
  return (
    // Sidebar container: fixed width, full height, white background with right border
    <aside className="w-72 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col h-full">

      {/* ── Branding ── */}
      <div className="p-4 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center flex-shrink-0">
            <span className="text-white text-lg">📄</span>
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-800 leading-tight">DocuMind</h1>
            <p className="text-xs text-slate-400">AI PDF Research Assistant</p>
          </div>
        </div>
      </div>

      {/* ── Scrollable content area ── */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">

        {/* ── Section: Upload ── */}
        <div>
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
            Document
          </h2>

          {/* Show uploader only when no document is loaded */}
          {!document && !isUploading && (
            <FileUploader onUpload={onUpload} isLoading={isUploading} />
          )}

          {/* Upload/processing loading state */}
          {isUploading && (
            <div className="border-2 border-dashed border-blue-200 rounded-xl p-6 text-center bg-blue-50">
              <div className="flex flex-col items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                  <svg className="w-5 h-5 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-blue-700">Processing PDF...</p>
                  <p className="text-xs text-blue-500 mt-0.5">
                    Extracting text, creating embeddings
                  </p>
                </div>
                <LoadingIndicator message="" size="sm" />
              </div>
            </div>
          )}

          {/* Upload error message */}
          {uploadError && !isUploading && (
            <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-start gap-2">
                <svg className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd"
                    d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                    clipRule="evenodd" />
                </svg>
                <p className="text-xs text-red-600">{uploadError}</p>
              </div>
              {/* Let user try again */}
              <button
                onClick={() => onUpload(null)}
                className="mt-2 w-full text-xs text-red-600 hover:text-red-800 font-medium"
              >
                Try again
              </button>
            </div>
          )}
        </div>

        {/* ── Section: Document info (shown after successful upload) ── */}
        {document && (
          <div className="space-y-3">
            {/* Document card */}
            <div className="p-3 bg-green-50 border border-green-200 rounded-xl">
              {/* Status header */}
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" />
                <span className="text-xs font-semibold text-green-700">Ready</span>
              </div>

              {/* Filename */}
              <div className="flex items-start gap-2">
                <svg className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                {/* truncate prevents long filenames from breaking the layout */}
                <p className="text-sm font-medium text-slate-700 truncate" title={document.filename}>
                  {document.filename}
                </p>
              </div>

              {/* Document stats */}
              <div className="mt-2 grid grid-cols-2 gap-2">
                <div className="bg-white rounded-lg p-2 text-center border border-green-100">
                  <p className="text-lg font-bold text-slate-800">{document.page_count}</p>
                  <p className="text-xs text-slate-400">Pages</p>
                </div>
                <div className="bg-white rounded-lg p-2 text-center border border-green-100">
                  <p className="text-lg font-bold text-slate-800">{document.chunk_count}</p>
                  <p className="text-xs text-slate-400">Chunks</p>
                </div>
              </div>
            </div>

            {/* Summarize button */}
            <button
              onClick={onSummarize}
              disabled={isSummarizing}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5
                bg-white border border-slate-200 rounded-xl text-sm font-medium
                text-slate-700 hover:bg-slate-50 hover:border-slate-300
                transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSummarizing ? (
                <LoadingIndicator message="Summarizing..." size="sm" />
              ) : (
                <>
                  <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M4 6h16M4 12h16M4 18h7" />
                  </svg>
                  Generate Summary
                </>
              )}
            </button>

            {/* Remove document button */}
            <button
              onClick={onRemove}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5
                bg-white border border-red-200 rounded-xl text-sm font-medium
                text-red-500 hover:bg-red-50 hover:border-red-300
                transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Remove Document
            </button>
          </div>
        )}

        {/* ── Usage tips ── */}
        {!document && !isUploading && (
          <div className="p-3 bg-blue-50 border border-blue-100 rounded-xl">
            <p className="text-xs font-semibold text-blue-700 mb-2">How it works</p>
            <ol className="text-xs text-blue-600 space-y-1 list-decimal list-inside">
              <li>Upload a PDF document</li>
              <li>Wait for processing</li>
              <li>Ask questions in natural language</li>
              <li>Get answers with page citations</li>
            </ol>
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      <div className="p-3 border-t border-slate-100">
        <p className="text-xs text-center text-slate-400">
          Powered by Gemini · FAISS · Sentence Transformers
        </p>
      </div>
    </aside>
  )
}
