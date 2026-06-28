/**
 * API Client — all backend calls centralized here
 * Auth token automatically injected into every request.
 */
const API_BASE = '';  // same origin — served by FastAPI

// ─── Auth Header Helper ───────────────────────────────────────────────────────
function _authHeaders(extra = {}) {
  const token = auth.getToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...extra,
  };
}

async function _handleResponse(res) {
  if (res.status === 401) {
    auth.logout();
    throw new Error('Session expired. Please login again.');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

const api = {
  // ─── Documents ─────────────────────────────────────────────────────────────
  async uploadDocument(file, onProgress) {
    const formData = new FormData();
    formData.append('file', file);
    const token = auth.getToken();

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/api/documents/upload`);
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else if (xhr.status === 401) {
          auth.logout();
          reject(new Error('Session expired'));
        } else {
          const err = JSON.parse(xhr.responseText || '{}');
          reject(new Error(err.detail || `Upload failed (${xhr.status})`));
        }
      };

      xhr.onerror = () => reject(new Error('Network error during upload'));
      xhr.send(formData);
    });
  },

  async listDocuments() {
    const res = await fetch(`${API_BASE}/api/documents`, { headers: _authHeaders() });
    return _handleResponse(res);
  },

  async deleteDocument(docId) {
    const res = await fetch(`${API_BASE}/api/documents/${docId}`, {
      method: 'DELETE',
      headers: _authHeaders(),
    });
    return _handleResponse(res);
  },

  async getStats() {
    const res = await fetch(`${API_BASE}/api/documents/stats`, { headers: _authHeaders() });
    return _handleResponse(res);
  },

  // ─── Conversations ──────────────────────────────────────────────────────────
  async listConversations() {
    const res = await fetch(`${API_BASE}/api/conversations`, { headers: _authHeaders() });
    return _handleResponse(res);
  },

  async createConversation(title = 'New Conversation') {
    const res = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: _authHeaders(),
      body: JSON.stringify({ title }),
    });
    return _handleResponse(res);
  },

  async getMessages(convId) {
    const res = await fetch(`${API_BASE}/api/conversations/${convId}/messages`, {
      headers: _authHeaders(),
    });
    return _handleResponse(res);
  },

  async deleteConversation(convId) {
    const res = await fetch(`${API_BASE}/api/conversations/${convId}`, {
      method: 'DELETE',
      headers: _authHeaders(),
    });
    return _handleResponse(res);
  },

  // ─── Sessions ───────────────────────────────────────────────────────────────
  async getSession(sessionId) {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, { headers: _authHeaders() });
    if (!res.ok) return null;
    return res.json();
  },

  async saveSession(sessionId, data) {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
      method: 'PUT',
      headers: _authHeaders(),
      body: JSON.stringify(data),
    });
    return _handleResponse(res);
  },

  // ─── Streaming Chat ─────────────────────────────────────────────────────────
  async streamChat({ conversationId, message, documentFilter, onStatus, onCitation, onToken, onDone, onError }) {
    const response = await fetch(`${API_BASE}/api/chat/stream`, {
      method: 'POST',
      headers: _authHeaders(),
      body: JSON.stringify({
        conversation_id: conversationId,
        message,
        document_filter: documentFilter || null,
      }),
    });

    if (response.status === 401) {
      auth.logout();
      onError?.('Session expired. Please login again.');
      return;
    }

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      onError?.(err.detail || 'Failed to connect to chat');
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed === 'data: [DONE]') continue;
        if (!trimmed.startsWith('data: ')) continue;

        try {
          const event = JSON.parse(trimmed.slice(6));
          switch (event.type) {
            case 'status':   onStatus?.(event.message); break;
            case 'citation': onCitation?.(event.data);  break;
            case 'token':    onToken?.(event.content);  break;
            case 'done':     onDone?.(event.answer, event.citations); break;
            case 'error':    onError?.(event.message);  break;
          }
        } catch (_) { /* ignore parse errors */ }
      }
    }
  },

  // ─── RAG Evaluation ────────────────────────────────────────────────────────
  async evaluate(question, answer, contexts) {
    const res = await fetch(`${API_BASE}/api/evaluate`, {
      method: 'POST',
      headers: _authHeaders(),
      body: JSON.stringify({ question, answer, contexts }),
    });
    return _handleResponse(res);
  },

  // ─── Health check ───────────────────────────────────────────────────────────
  async checkHealth() {
    try {
      const res = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(3000) });
      return res.ok;
    } catch {
      return false;
    }
  },
};
