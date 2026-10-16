/*
  FileUploader.jsx

  A drag-and-drop PDF upload component.

  What it does:
  - Accepts drag-and-drop or click-to-browse file selection
  - Validates that the file is a PDF (by MIME type and extension)
  - Calls the onUpload callback with the selected File object
  - Shows a disabled state while an upload is in progress

  Props:
  - onUpload:  (file: File) => void  — called when a valid PDF is selected
  - isLoading: boolean               — disables the input during upload

  It does NOT make the API call itself — that's the parent component's job.
  This separation makes FileUploader reusable and easy to test.
*/

import { useState, useRef } from 'react'

export default function FileUploader({ onUpload, isLoading }) {
  // Whether the user is dragging a file over the drop zone
  const [isDragging, setIsDragging] = useState(false)
  // Validation error message, if any
  const [error, setError] = useState(null)

  // Ref to the hidden <input type="file"> element
  // We trigger it programmatically when the user clicks the drop zone
  const fileInputRef = useRef(null)

  // ── Validation ──────────────────────────────────────────────
  const validateFile = (file) => {
    if (!file) return 'No file selected'

    // Check MIME type — browsers report PDF as 'application/pdf'
    const isPdf = file.type === 'application/pdf'
    // Also check the extension as a fallback (some systems report wrong MIME)
    const hasPdfExtension = file.name.toLowerCase().endsWith('.pdf')

    if (!isPdf && !hasPdfExtension) {
      return 'Please select a PDF file (.pdf)'
    }

    const maxSize = 10 * 1024 * 1024
    if (file.size > maxSize) {
      return `File too large. Maximum size is 10 MB (your file: ${(file.size / 1024 / 1024).toFixed(1)} MB)`
    }

    if (file.size === 0) {
      return 'The selected file is empty'
    }

    return null // null means valid
  }

  // ── Handle file selection ────────────────────────────────────
  const handleFile = (file) => {
    setError(null)
    const validationError = validateFile(file)
    if (validationError) {
      setError(validationError)
      return
    }
    // Pass the valid file up to the parent
    onUpload(file)
  }

  // ── Drag events ──────────────────────────────────────────────
  const handleDragOver = (e) => {
    e.preventDefault() // required to allow dropping
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    handleFile(file)
  }

  // ── Input change (click-to-browse) ───────────────────────────
  const handleInputChange = (e) => {
    const file = e.target.files[0]
    if (file) handleFile(file)
    // Reset input so the same file can be re-selected if needed
    e.target.value = ''
  }

  return (
    <div>
      {/* Drop zone */}
      <div
        onClick={() => !isLoading && fileInputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-xl p-6 text-center cursor-pointer
          transition-all duration-200
          ${isLoading
            ? 'border-slate-200 bg-slate-50 cursor-not-allowed opacity-60'
            : isDragging
              ? 'border-blue-400 bg-blue-50'
              : 'border-slate-300 bg-white hover:border-blue-400 hover:bg-blue-50'
          }
        `}
        role="button"
        tabIndex={0}
        aria-label="Upload PDF file"
        // Allow keyboard activation
        onKeyDown={(e) => e.key === 'Enter' && !isLoading && fileInputRef.current?.click()}
      >
        {/* Upload icon */}
        <div className="flex flex-col items-center gap-2">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center
            ${isDragging ? 'bg-blue-100' : 'bg-slate-100'}`}>
            <svg className={`w-5 h-5 ${isDragging ? 'text-blue-500' : 'text-slate-400'}`}
              fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>

          <div>
            <p className="text-sm font-medium text-slate-700">
              {isDragging ? 'Drop your PDF here' : 'Upload PDF'}
            </p>
            <p className="text-xs text-slate-400 mt-0.5">
              Drag & drop or click to browse
            </p>
            <p className="text-xs text-slate-400">
              PDF only · Max 10 MB
            </p>
          </div>
        </div>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleInputChange}
          className="hidden"
          disabled={isLoading}
          aria-hidden="true"
        />
      </div>

      {/* Validation error */}
      {error && (
        <div className="mt-2 flex items-start gap-2 text-xs text-red-600 bg-red-50
          border border-red-200 rounded-lg px-3 py-2">
          <svg className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd" />
          </svg>
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}
