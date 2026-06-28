/**
 * Upload Module
 * Handles drag & drop, file validation, upload queue UI
 */

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp'];
const MAX_SIZE_MB = 50;

const FILE_ICONS = {
  pdf:   '📕',
  docx:  '📘',
  xlsx:  '📗',
  image: '🖼️',
};

const FILE_TYPE_MAP = {
  '.pdf': 'pdf', '.docx': 'docx', '.doc': 'docx',
  '.xlsx': 'xlsx', '.xls': 'xlsx',
  '.png': 'image', '.jpg': 'image', '.jpeg': 'image',
  '.gif': 'image', '.bmp': 'image', '.tiff': 'image', '.webp': 'image',
};

function getFileType(name) {
  const ext = '.' + name.split('.').pop().toLowerCase();
  return FILE_TYPE_MAP[ext] || 'unknown';
}

function formatBytes(bytes) {
  if (bytes < 1024)       return bytes + ' B';
  if (bytes < 1024*1024)  return (bytes/1024).toFixed(1) + ' KB';
  return (bytes/(1024*1024)).toFixed(1) + ' MB';
}

function validateFile(file) {
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return `Unsupported file type: ${ext}. Allowed: PDF, DOCX, XLSX, Images`;
  }
  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    return `File too large: ${formatBytes(file.size)}. Max ${MAX_SIZE_MB}MB`;
  }
  return null;
}

function createQueueItem(file) {
  const fileType = getFileType(file.name);
  const icon = FILE_ICONS[fileType] || '📄';

  const item = document.createElement('div');
  item.className = 'queue-item';
  item.innerHTML = `
    <div class="doc-type-icon doc-type-${fileType}">${icon}</div>
    <div style="flex:1;min-width:0;">
      <div class="doc-name">${file.name}</div>
      <div class="doc-info">${formatBytes(file.size)} · ${fileType.toUpperCase()}</div>
      <div class="queue-progress-bar" style="display:none">
        <div class="queue-progress-fill" style="width:0%"></div>
      </div>
    </div>
    <div class="doc-status processing" style="font-size:0.7rem;">Pending</div>
  `;
  return item;
}

async function uploadFiles(files, queueContainer) {
  const validFiles = [];

  for (const file of files) {
    const err = validateFile(file);
    if (err) {
      showToast(err, 'error');
      continue;
    }
    validFiles.push(file);
  }

  if (!validFiles.length) return;

  for (const file of validFiles) {
    const item = createQueueItem(file);
    queueContainer.appendChild(item);
    const statusBadge = item.querySelector('.doc-status');
    const progressBar = item.querySelector('.queue-progress-bar');
    const progressFill = item.querySelector('.queue-progress-fill');

    try {
      statusBadge.textContent = 'Uploading...';
      statusBadge.className = 'doc-status processing';
      item.classList.add('uploading');
      progressBar.style.display = 'block';

      await api.uploadDocument(file, (pct) => {
        progressFill.style.width = pct + '%';
      });

      progressFill.style.width = '100%';
      statusBadge.textContent = 'Processing...';
      showToast(`"${file.name}" uploaded! Processing in background...`, 'success');

      // Refresh document list
      setTimeout(() => {
        loadDocuments();
        loadStats();
      }, 1000);

      // Keep polling until ready
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        if (attempts > 60) { clearInterval(poll); return; }
        const docs = await api.listDocuments().catch(() => []);
        const doc = docs.find(d => d.original_filename === file.name);
        if (doc?.status === 'ready') {
          clearInterval(poll);
          statusBadge.textContent = 'Ready ✓';
          statusBadge.className = 'doc-status ready';
          item.classList.remove('uploading');
          progressBar.style.display = 'none';
          loadDocuments();
          loadStats();
        } else if (doc?.status === 'error') {
          clearInterval(poll);
          statusBadge.textContent = 'Error';
          statusBadge.className = 'doc-status error';
          item.classList.remove('uploading');
        }
      }, 3000);

    } catch (err) {
      statusBadge.textContent = 'Failed';
      statusBadge.className = 'doc-status error';
      item.classList.remove('uploading');
      progressBar.style.display = 'none';
      showToast(`Upload failed: ${err.message}`, 'error');
    }
  }
}

function setupUploadZone(zoneEl, inputEl, queueEl) {
  // Click to upload
  inputEl.addEventListener('change', (e) => {
    uploadFiles(Array.from(e.target.files), queueEl);
    inputEl.value = '';
  });

  // Drag & Drop
  zoneEl.addEventListener('dragover', (e) => {
    e.preventDefault();
    zoneEl.classList.add('drag-over');
  });

  zoneEl.addEventListener('dragleave', () => {
    zoneEl.classList.remove('drag-over');
  });

  zoneEl.addEventListener('drop', (e) => {
    e.preventDefault();
    zoneEl.classList.remove('drag-over');
    const files = Array.from(e.dataTransfer.files);
    uploadFiles(files, queueEl);
  });

  // Paste support (for images)
  document.addEventListener('paste', (e) => {
    const items = Array.from(e.clipboardData.items || []);
    const imageFiles = items
      .filter(item => item.kind === 'file' && item.type.startsWith('image/'))
      .map(item => item.getAsFile())
      .filter(Boolean);
    if (imageFiles.length) {
      uploadFiles(imageFiles, queueEl);
    }
  });
}
