/**
 * Auth Module — Login, Register, Logout
 * Stores JWT in localStorage under 'auth_token'
 * Exposes: auth.getToken(), auth.getUser(), auth.logout(), auth.isLoggedIn()
 */

const TOKEN_KEY = 'auth_token';
const USER_KEY  = 'auth_user';

const auth = {
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },

  getUser() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
    } catch {
      return null;
    }
  },

  isLoggedIn() {
    return !!this.getToken();
  },

  _saveSession(data) {
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify({ username: data.username }));
  },

  logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem('rag_session_id');
    location.reload();
  },

  async register(username, password) {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Registration failed');
    this._saveSession(data);
    return data;
  },

  async login(username, password) {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Login failed');
    this._saveSession(data);
    return data;
  },

  async verifyToken() {
    const token = this.getToken();
    if (!token) return false;
    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { 'Authorization': `Bearer ${token}` },
        signal: AbortSignal.timeout(5000),
      });
      return res.ok;
    } catch {
      return false;
    }
  },
};

// ─── Auth UI ──────────────────────────────────────────────────────────────────

function showAuthScreen() {
  const overlay = document.getElementById('auth-overlay');
  if (overlay) overlay.classList.add('active');
}

function hideAuthScreen() {
  const overlay = document.getElementById('auth-overlay');
  if (overlay) overlay.classList.remove('active');
}

function switchAuthTab(tab) {
  document.querySelectorAll('.auth-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tab);
  });
  document.querySelectorAll('.auth-form-panel').forEach(panel => {
    panel.classList.toggle('active', panel.dataset.form === tab);
  });
}

async function handleLogin(e) {
  e.preventDefault();
  const btn    = document.getElementById('login-btn');
  const errEl  = document.getElementById('login-error');
  const user   = document.getElementById('login-username').value.trim();
  const pass   = document.getElementById('login-password').value;

  if (!user || !pass) {
    errEl.textContent = 'Please enter username and password.';
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Signing in…';
  errEl.textContent = '';

  try {
    await auth.login(user, pass);
    hideAuthScreen();
    await initApp();
  } catch (err) {
    errEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign In';
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const btn    = document.getElementById('register-btn');
  const errEl  = document.getElementById('register-error');
  const user   = document.getElementById('register-username').value.trim();
  const pass   = document.getElementById('register-password').value;
  const pass2  = document.getElementById('register-password2').value;

  if (!user || !pass) {
    errEl.textContent = 'Please fill in all fields.';
    return;
  }
  if (pass !== pass2) {
    errEl.textContent = 'Passwords do not match.';
    return;
  }
  if (pass.length < 6) {
    errEl.textContent = 'Password must be at least 6 characters.';
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Creating account…';
  errEl.textContent = '';

  try {
    await auth.register(user, pass);
    hideAuthScreen();
    await initApp();
  } catch (err) {
    errEl.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Create Account';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // Wire up auth form events
  document.getElementById('login-form')?.addEventListener('submit', handleLogin);
  document.getElementById('register-form')?.addEventListener('submit', handleRegister);
  document.querySelectorAll('.auth-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchAuthTab(btn.dataset.tab));
  });
});
