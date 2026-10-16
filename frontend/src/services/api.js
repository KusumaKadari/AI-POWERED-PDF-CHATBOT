const API_BASE = ''

async function request(path, options, fallbackMessage) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, options)
  } catch {
    throw new Error('Cannot reach the backend. Check that the API server is running.')
  }

  let data
  try {
    data = await response.json()
  } catch {
    throw new Error(fallbackMessage)
  }

  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : fallbackMessage
    throw new Error(detail)
  }

  return data
}

export async function checkHealth() {
  return request('/api/health', undefined, 'Backend health check failed.')
}

export async function uploadDocument(file) {
  const formData = new FormData()
  formData.append('file', file)

  return request('/api/documents/upload', {
    method: 'POST',
    body: formData,
  }, 'Upload failed. Check that the file is a valid PDF and within the size limit.')
}

export async function deleteDocument(documentId) {
  return request(`/api/documents/${encodeURIComponent(documentId)}`, {
    method: 'DELETE',
  }, 'Could not remove the document.')
}

export async function askQuestion(documentId, question) {
  return request('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      document_id: documentId,
      question,
    }),
  }, 'Could not get an answer. Please try again.')
}

export async function summarizeDocument(documentId) {
  return request(`/api/documents/${encodeURIComponent(documentId)}/summary`, {
    method: 'POST',
  }, 'Could not summarize the document. Please try again.')
}
