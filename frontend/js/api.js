/**
 * API Client — all backend calls centralized here
 */
const API_BASE = 'http://localhost:8000';

const api = {
  // ─── Documents ───────────────────────────────────────────────
  async uploadDocument(file, onProgress) {
    const formData = new FormData();
    formData.append('file', file);

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/api/documents/upload`);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
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
    const res = await fetch(`${API_BASE}/api/documents`);
    if (!res.ok) throw new Error('Failed to fetch documents');
    return res.json();
  },

  async deleteDocument(docId) {
    const res = await fetch(`${API_BASE}/api/documents/${docId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete document');
    return res.json();
  },

  async getStats() {
    const res = await fetch(`${API_BASE}/api/documents/stats`);
    if (!res.ok) throw new Error('Failed to fetch stats');
    return res.json();
  },

  // ─── Conversations ────────────────────────────────────────────
  async listConversations() {
    const res = await fetch(`${API_BASE}/api/conversations`);
    if (!res.ok) throw new Error('Failed to fetch conversations');
    return res.json();
  },

  async createConversation(title = 'New Conversation') {
    const res = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    });
    if (!res.ok) throw new Error('Failed to create conversation');
    return res.json();
  },

  async getMessages(convId) {
    const res = await fetch(`${API_BASE}/api/conversations/${convId}/messages`);
    if (!res.ok) throw new Error('Failed to fetch messages');
    return res.json();
  },

  async deleteConversation(convId) {
    const res = await fetch(`${API_BASE}/api/conversations/${convId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete conversation');
    return res.json();
  },

  // ─── Sessions ─────────────────────────────────────────────────
  async getSession(sessionId) {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`);
    if (!res.ok) return null;
    return res.json();
  },

  async saveSession(sessionId, data) {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to save session');
    return res.json();
  },

  // ─── Streaming Chat ───────────────────────────────────────────
  /**
   * Stream chat response via SSE.
   * @param {Object} opts
   * @param {string} opts.conversationId
   * @param {string} opts.message
   * @param {string[]|null} opts.documentFilter
   * @param {Function} opts.onStatus   - (message: string) => void
   * @param {Function} opts.onCitation - (citations: Array) => void
   * @param {Function} opts.onToken    - (token: string) => void
   * @param {Function} opts.onDone     - (answer: string, citations: Array) => void
   * @param {Function} opts.onError    - (err: string) => void
   */
  async streamChat({ conversationId, message, documentFilter, onStatus, onCitation, onToken, onDone, onError }) {
    const response = await fetch(`${API_BASE}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: conversationId,
        message,
        document_filter: documentFilter || null,
      }),
    });

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
      buffer = lines.pop(); // keep incomplete line

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

  // ─── Health check ─────────────────────────────────────────────
  async checkHealth() {
    try {
      const res = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(3000) });
      return res.ok;
    } catch {
      return false;
    }
  },
};
