/**
 * App Module — Initialization and global UI logic
 */

const SESSION_KEY = 'rag_session_id';
let sessionId = null;

// ─── Initialization ────────────────────────────────────────────────────────────

async function initApp() {
  // Check backend health first
  const healthy = await api.checkHealth();
  if (!healthy) {
    showBackendError();
    hideLoader();
    return;
  }

  // Gate on authentication
  const loggedIn = auth.isLoggedIn() && await auth.verifyToken();
  if (!loggedIn) {
    // Clear stale token WITHOUT reloading the page
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    showAuthScreen();
    hideLoader();
    return;
  }

  // Show user info in header
  const user = auth.getUser();
  const userBadge = document.getElementById('user-badge');
  const userBadgeName = document.getElementById('user-badge-name');
  if (userBadge && user) {
    userBadgeName.textContent = user.username;
    userBadge.style.display = 'flex';
  }

  // Get or create session ID
  sessionId = localStorage.getItem(SESSION_KEY);
  if (!sessionId) {
    sessionId = 'sess_' + Math.random().toString(36).slice(2) + Date.now();
    localStorage.setItem(SESSION_KEY, sessionId);
  }

  // Load initial data in parallel
  await Promise.all([
    loadConversations(),
    loadDocuments(),
    loadStats(),
  ]);

  // Restore session state
  try {
    const session = await api.getSession(sessionId);
    if (session?.active_conversation_id) {
      const conv = allConversations.find(c => c.id === session.active_conversation_id);
      if (conv) await openConversation(conv.id);
    }
    if (session?.document_filter) {
      selectedDocFilter = session.document_filter;
      renderFilterChips();
    }
  } catch (_) {}

  // Setup upload zones
  setupUploadZone(
    document.getElementById('sidebar-upload-zone'),
    document.getElementById('sidebar-file-input'),
    document.getElementById('sidebar-upload-queue'),
  );

  // Auto-refresh every 30s
  setInterval(() => { loadDocuments(); loadStats(); }, 30000);

  hideLoader();
}

function hideLoader() {
  const overlay = document.getElementById('loading-overlay');
  if (!overlay) return;
  overlay.style.opacity = '0';
  setTimeout(() => overlay.remove(), 400);
}

function showBackendError() {
  const overlay = document.getElementById('loading-overlay');
  overlay.innerHTML = `
    <div style="text-align:center;max-width:400px;padding:32px;">
      <div style="font-size:48px;margin-bottom:16px;">⚠️</div>
      <h2 style="color:var(--text-primary);margin-bottom:8px;font-size:1.2rem;">Backend Not Running</h2>
      <p style="color:var(--text-muted);font-size:0.85rem;line-height:1.6;">
        The AI backend is not reachable at <code style="color:var(--accent-primary)">http://localhost:8000</code>.
        <br><br>
        Please run <code style="color:var(--accent-primary)">start.bat</code> or start the backend manually.
      </p>
      <button class="btn btn-primary" style="margin-top:20px;" onclick="location.reload()">🔄 Retry Connection</button>
    </div>
  `;
}

// ─── Sidebar Tab Switching ────────────────────────────────────────────────────

function switchSidebarTab(tab) {
  const tabs = ['chats', 'docs', 'upload'];
  tabs.forEach(t => {
    document.getElementById(`tab-${t}`)?.classList.toggle('active', t === tab);
    document.getElementById(`panel-${t}`)?.classList.toggle('active', t === tab);
  });
}

// ─── Session Persistence ──────────────────────────────────────────────────────

function saveSessionState() {
  if (!sessionId || !auth.isLoggedIn()) return;
  api.saveSession(sessionId, {
    session_id: sessionId,
    active_conversation_id: currentConvId,
    document_filter: selectedDocFilter,
  }).catch(() => {});
}

window.addEventListener('beforeunload', saveSessionState);

// ─── Toast Notifications ──────────────────────────────────────────────────────

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span style="flex-shrink:0">${icons[type] || 'ℹ️'}</span>
    <span style="flex:1">${message}</span>
    <button onclick="this.parentElement.remove()" style="background:none;color:var(--text-muted);font-size:14px;padding:2px 4px;">✕</button>
  `;
  container.appendChild(toast);

  const duration = type === 'error' ? 6000 : 3500;
  setTimeout(() => {
    if (toast.parentElement) {
      toast.style.animation = 'toast-out 0.3s ease forwards';
      setTimeout(() => toast.remove(), 300);
    }
  }, duration);
}

// ─── Boot ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', initApp);
