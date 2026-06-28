/**
 * Chat Module
 * Handles message rendering, streaming, citations, and conversation state
 */

let currentConvId = null;
let isStreaming = false;
let allConversations = [];

// ─── Conversation Management ──────────────────────────────────

async function loadConversations() {
  try {
    allConversations = await api.listConversations();
    renderConvList();
    document.getElementById('stat-convs').textContent = allConversations.length;
  } catch (err) {
    console.error('Failed to load conversations:', err);
  }
}

function renderConvList() {
  const container = document.getElementById('conv-list');
  if (!allConversations.length) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">💬</div>
        <p>No conversations yet.<br>Start chatting!</p>
      </div>`;
    return;
  }

  container.innerHTML = allConversations.map(conv => `
    <div class="conv-item ${conv.id === currentConvId ? 'active' : ''}" onclick="openConversation('${conv.id}')">
      <span class="conv-icon">💬</span>
      <div class="conv-info">
        <div class="conv-title" title="${conv.title}">${conv.title}</div>
        <div class="conv-time">${formatRelativeTime(conv.updated_at)}</div>
      </div>
      <button class="conv-delete" onclick="deleteConv('${conv.id}', event)" title="Delete">✕</button>
    </div>
  `).join('');
}

function formatRelativeTime(dateStr) {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1)   return 'just now';
  if (diffMins < 60)  return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7)   return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

async function startNewChat() {
  try {
    const conv = await api.createConversation('New Conversation');
    allConversations.unshift(conv);
    await openConversation(conv.id);
    renderConvList();
    // Switch to chats tab
    switchSidebarTab('chats');
  } catch (err) {
    showToast('Failed to create conversation: ' + err.message, 'error');
  }
}

async function openConversation(convId) {
  currentConvId = convId;
  renderConvList();

  // Update topbar
  const conv = allConversations.find(c => c.id === convId);
  if (conv) {
    document.getElementById('topbar-conv-title').textContent = conv.title;
    document.getElementById('topbar-conv-subtitle').textContent = `Conversation · ${formatRelativeTime(conv.updated_at)}`;
  }

  document.getElementById('btn-clear-chat').style.display = 'flex';

  // Show messages container, hide welcome
  document.getElementById('welcome-screen').style.display = 'none';
  const messagesEl = document.getElementById('messages');
  messagesEl.style.display = 'flex';
  messagesEl.innerHTML = '';

  try {
    const messages = await api.getMessages(convId);
    for (const msg of messages) {
      if (msg.role === 'user') {
        appendUserMessage(msg.content);
      } else {
        appendAIMessage(msg.content, msg.citations || []);
      }
    }
    scrollToBottom();
  } catch (err) {
    showToast('Failed to load messages', 'error');
  }

  // Update session
  saveSessionState();

  // Focus input
  document.getElementById('chat-input').focus();
}

async function deleteConv(convId, event) {
  event.stopPropagation();
  if (!confirm('Delete this conversation?')) return;
  try {
    await api.deleteConversation(convId);
    allConversations = allConversations.filter(c => c.id !== convId);
    if (currentConvId === convId) {
      currentConvId = null;
      document.getElementById('welcome-screen').style.display = 'flex';
      document.getElementById('messages').style.display = 'none';
      document.getElementById('btn-clear-chat').style.display = 'none';
      document.getElementById('topbar-conv-title').textContent = 'Enterprise Knowledge Assistant';
      document.getElementById('topbar-conv-subtitle').textContent = 'Upload documents and start asking questions';
    }
    renderConvList();
    showToast('Conversation deleted', 'info');
  } catch (err) {
    showToast('Delete failed: ' + err.message, 'error');
  }
}

async function clearCurrentChat() {
  if (!currentConvId) return;
  if (!confirm('Clear this conversation?')) return;
  await deleteConv(currentConvId, { stopPropagation: () => {} });
}

// ─── Message Rendering ────────────────────────────────────────

function appendUserMessage(text) {
  const messagesEl = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'message-row user';
  div.innerHTML = `
    <div class="msg-bubble user">${escapeHtml(text)}</div>
    <div class="msg-avatar user">👤</div>
  `;
  messagesEl.appendChild(div);
  scrollToBottom();
}

function appendAIMessage(text, citations = []) {
  const messagesEl = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'message-row';
  div.innerHTML = `
    <div class="msg-avatar ai">🧠</div>
    <div class="msg-bubble ai">
      <div class="msg-content">${renderMarkdown(text)}</div>
      ${citations.length ? renderCitations(citations) : ''}
    </div>
  `;
  messagesEl.appendChild(div);
  scrollToBottom();
}

function createStreamingMessage() {
  const messagesEl = document.getElementById('messages');

  // Status row
  const statusRow = document.createElement('div');
  statusRow.className = 'msg-status';
  statusRow.id = 'stream-status';
  statusRow.innerHTML = `<div class="status-dot"></div><span id="stream-status-text">Searching documents...</span>`;
  messagesEl.appendChild(statusRow);

  // Message row
  const msgRow = document.createElement('div');
  msgRow.className = 'message-row';
  msgRow.id = 'stream-message';
  msgRow.style.display = 'none';
  msgRow.innerHTML = `
    <div class="msg-avatar ai">🧠</div>
    <div class="msg-bubble ai">
      <div class="msg-content" id="stream-content">
        <div class="typing-dots">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
      <div id="stream-citations"></div>
    </div>
  `;
  messagesEl.appendChild(msgRow);
  scrollToBottom();

  return {
    setStatus(text) {
      document.getElementById('stream-status-text').textContent = text;
    },
    showMessage() {
      msgRow.style.display = 'flex';
      document.getElementById('stream-content').innerHTML = '';
    },
    appendToken(token) {
      const contentEl = document.getElementById('stream-content');
      contentEl.textContent += token;  // raw text during streaming
    },
    setCitations(citations) {
      const el = document.getElementById('stream-citations');
      el.innerHTML = citations.length ? renderCitations(citations) : '';
    },
    finalize(fullText, citations) {
      // Remove status
      const statusEl = document.getElementById('stream-status');
      if (statusEl) statusEl.remove();
      // Render final markdown
      const contentEl = document.getElementById('stream-content');
      if (contentEl) contentEl.innerHTML = renderMarkdown(fullText);
      // Final citations
      const citEl = document.getElementById('stream-citations');
      if (citEl) citEl.innerHTML = citations.length ? renderCitations(citations) : '';
      scrollToBottom();
    },
    remove() {
      statusRow.remove();
      msgRow.remove();
    }
  };
}

function renderCitations(citations) {
  if (!citations || !citations.length) return '';
  return `
    <div class="citations-block">
      <div class="citations-title">📎 Sources</div>
      <div class="citation-cards">
        ${citations.map((c, i) => `
          <div class="citation-card" title="${c.filename} — Page ${c.page}">
            <div class="citation-header">
              <div class="cite-idx">${i + 1}</div>
              <div class="cite-file">${c.filename}</div>
              <div class="cite-page">p.${c.page}</div>
            </div>
            <div class="cite-text">${escapeHtml(c.chunk_text || '')}</div>
          </div>
        `).join('')}
      </div>
    </div>`;
}

function renderMarkdown(text) {
  if (!text) return '';
  // Simple markdown renderer
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}

function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─── Sending Messages ─────────────────────────────────────────

async function sendMessage() {
  if (isStreaming) return;

  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;

  // Ensure we have a conversation
  if (!currentConvId) {
    await startNewChat();
    if (!currentConvId) return;
  }

  // Clear input & resize
  input.value = '';
  autoResize(input);

  // Show messages area
  document.getElementById('welcome-screen').style.display = 'none';
  const messagesEl = document.getElementById('messages');
  messagesEl.style.display = 'flex';

  // Render user message
  appendUserMessage(text);

  // Disable input
  isStreaming = true;
  const sendBtn = document.getElementById('btn-send');
  sendBtn.disabled = true;
  input.disabled = true;

  // Create streaming message placeholder
  const stream = createStreamingMessage();
  let firstToken = true;
  let finalCitations = [];

  try {
    await api.streamChat({
      conversationId: currentConvId,
      message: text,
      documentFilter: selectedDocFilter.length ? selectedDocFilter : null,

      onStatus(message) {
        stream.setStatus(message);
      },

      onCitation(citations) {
        finalCitations = citations;
        stream.setCitations(citations);
      },

      onToken(token) {
        if (firstToken) {
          stream.showMessage();
          firstToken = false;
        }
        stream.appendToken(token);
        scrollToBottom();
      },

      onDone(answer, citations) {
        if (citations && citations.length) finalCitations = citations;
        stream.finalize(answer, finalCitations);

        // Refresh conversation list (title may have changed)
        loadConversations();
      },

      onError(message) {
        stream.remove();
        appendAIMessage(`❌ Error: ${message}`, []);
        showToast('Chat error: ' + message, 'error');
      },
    });

  } catch (err) {
    stream.remove();
    appendAIMessage(`❌ Failed to connect to AI service. Make sure the backend is running.`, []);
    showToast('Connection error: ' + err.message, 'error');
  } finally {
    isStreaming = false;
    sendBtn.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

function sendExampleQuery(text) {
  document.getElementById('chat-input').value = text;
  sendMessage();
}

function handleInputKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
}

function autoResize(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 160) + 'px';
}

function scrollToBottom() {
  const el = document.getElementById('messages');
  if (el) el.scrollTop = el.scrollHeight;
}
