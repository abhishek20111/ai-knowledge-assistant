/**
 * Documents Module
 * Renders document list in sidebar, manages doc filters
 */

let allDocuments = [];
let selectedDocFilter = [];  // array of doc IDs to filter by

async function loadDocuments() {
  try {
    allDocuments = await api.listDocuments();
    renderDocList();
  } catch (err) {
    console.error('Failed to load documents:', err);
  }
}

function renderDocList() {
  const container = document.getElementById('doc-list');
  if (!allDocuments.length) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📂</div>
        <p>No documents uploaded.<br>Upload files to get started!</p>
      </div>`;
    return;
  }

  container.innerHTML = allDocuments.map(doc => `
    <div class="doc-item" data-id="${doc.id}">
      <div class="doc-header">
        <div class="doc-type-icon doc-type-${doc.file_type}">
          ${getDocIcon(doc.file_type)}
        </div>
        <div class="doc-meta">
          <div class="doc-name" title="${doc.original_filename}">${doc.original_filename}</div>
          <div class="doc-info">
            ${formatBytes(doc.file_size)}
            ${doc.status === 'ready' ? ` · ${doc.page_count} pages · ${doc.chunk_count} chunks` : ''}
          </div>
        </div>
        <span class="doc-status ${doc.status}">${getStatusLabel(doc.status)}</span>
        <button class="doc-delete" onclick="deleteDoc('${doc.id}', event)" title="Delete document">🗑️</button>
      </div>
      ${doc.status === 'ready' ? `
      <div style="margin-top:8px;">
        <button
          class="btn btn-ghost"
          style="font-size:0.72rem;padding:4px 10px;width:100%;"
          onclick="toggleDocFilter('${doc.id}', '${doc.original_filename}')"
          id="filter-btn-${doc.id}"
        >
          ${selectedDocFilter.includes(doc.id) ? '✅ Filtering active' : '🔍 Filter chat to this doc'}
        </button>
      </div>` : ''}
    </div>
  `).join('');
}

function getDocIcon(type) {
  const icons = { pdf: '📕', docx: '📘', xlsx: '📗', image: '🖼️' };
  return icons[type] || '📄';
}

function getStatusLabel(status) {
  const labels = { ready: '✓ Ready', processing: '⏳ Processing', error: '✗ Error' };
  return labels[status] || status;
}

function formatBytes(bytes) {
  if (bytes < 1024)       return bytes + ' B';
  if (bytes < 1024*1024)  return (bytes/1024).toFixed(1) + ' KB';
  return (bytes/(1024*1024)).toFixed(1) + ' MB';
}

async function deleteDoc(docId, event) {
  event.stopPropagation();
  if (!confirm('Delete this document and all its data?')) return;
  try {
    await api.deleteDocument(docId);
    showToast('Document deleted', 'success');

    // Remove from filter if active
    selectedDocFilter = selectedDocFilter.filter(id => id !== docId);
    renderFilterChips();

    await loadDocuments();
    await loadStats();
  } catch (err) {
    showToast('Delete failed: ' + err.message, 'error');
  }
}

function toggleDocFilter(docId, docName) {
  const idx = selectedDocFilter.indexOf(docId);
  if (idx >= 0) {
    selectedDocFilter.splice(idx, 1);
  } else {
    selectedDocFilter.push(docId);
  }
  renderFilterChips();
  renderDocList();  // re-render to update button state
}

function renderFilterChips() {
  const container = document.getElementById('doc-filter-chips');
  if (!selectedDocFilter.length) {
    container.innerHTML = '';
    return;
  }

  container.innerHTML = selectedDocFilter.map(id => {
    const doc = allDocuments.find(d => d.id === id);
    const name = doc ? doc.original_filename : id;
    const shortName = name.length > 20 ? name.slice(0, 18) + '…' : name;
    return `
      <div class="filter-chip" title="${name}">
        🔍 ${shortName}
        <span class="chip-remove" onclick="toggleDocFilter('${id}')">✕</span>
      </div>`;
  }).join('');
}

async function loadStats() {
  try {
    const [stats, convs] = await Promise.all([
      api.getStats(),
      api.listConversations(),
    ]);
    document.getElementById('stat-docs').textContent = stats.total_documents || 0;
    document.getElementById('stat-chunks').textContent = formatChunkCount(stats.child_chunks || 0);
    document.getElementById('stat-convs').textContent = convs.length || 0;
  } catch (err) {
    console.warn('Stats load failed:', err);
  }
}

function formatChunkCount(n) {
  if (n >= 1000) return (n/1000).toFixed(1) + 'k';
  return n;
}
