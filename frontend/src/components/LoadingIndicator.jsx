/*
  LoadingIndicator.jsx

  Shows an animated "typing" indicator while the backend is processing.
  Used in two places:
  1. Inside the chat window while waiting for an AI answer
  2. In the sidebar while a PDF is being uploaded and processed

  Props:
  - message (string, optional) — text to show next to the dots
  - size    ('sm' | 'md')      — controls dot size, defaults to 'md'
*/

export default function LoadingIndicator({ message = 'Thinking...', size = 'md' }) {
  const dotSize = size === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2'

  return (
    <div className="flex items-center gap-2">
      {/* Three animated dots */}
      {/* Each dot has a different animation-delay so they bounce in sequence */}
      <div className="flex items-center gap-1">
        <span
          className={`${dotSize} bg-blue-400 rounded-full inline-block animate-bounce`}
          style={{ animationDelay: '0ms' }}
        />
        <span
          className={`${dotSize} bg-blue-400 rounded-full inline-block animate-bounce`}
          style={{ animationDelay: '150ms' }}
        />
        <span
          className={`${dotSize} bg-blue-400 rounded-full inline-block animate-bounce`}
          style={{ animationDelay: '300ms' }}
        />
      </div>

      {/* Optional message text */}
      {message && (
        <span className="text-sm text-slate-500 italic">{message}</span>
      )}
    </div>
  )
}
