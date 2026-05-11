const API = '/api/bookmarks';

let allBookmarks = [];
let allTags = [];
let activeTag = null;
let searchQuery = '';
let pendingDeleteId = null;

// ── DOM refs ──────────────────────────────────────────
const grid         = document.getElementById('bookmarksGrid');
const emptyState   = document.getElementById('emptyState');
const emptyMsg     = document.getElementById('emptyMessage');
const resultCount  = document.getElementById('resultCount');
const tagsBar      = document.getElementById('tagsBar');
const clearFilterBtn = document.getElementById('clearFilterBtn');

const searchInput  = document.getElementById('searchInput');
const searchClear  = document.getElementById('searchClear');

const overlay      = document.getElementById('overlay');
const modalTitle   = document.getElementById('modalTitle');
const bookmarkForm = document.getElementById('bookmarkForm');
const editId       = document.getElementById('editId');
const urlInput     = document.getElementById('urlInput');
const titleInput   = document.getElementById('titleInput');
const descInput    = document.getElementById('descInput');
const tagsInput    = document.getElementById('tagsInput');
const urlError     = document.getElementById('urlError');
const titleError   = document.getElementById('titleError');

const deleteOverlay     = document.getElementById('deleteOverlay');
const deleteTitle       = document.getElementById('deleteTitle');
const deleteConfirmBtn  = document.getElementById('deleteConfirmBtn');

const toast = document.getElementById('toast');

// ── API helpers ───────────────────────────────────────
async function apiFetch(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

// ── Data loading ──────────────────────────────────────
async function loadBookmarks() {
  const params = new URLSearchParams();
  if (searchQuery) params.set('search', searchQuery);
  if (activeTag)   params.set('tag', activeTag);
  const qs = params.toString();
  allBookmarks = await apiFetch(`${API}${qs ? '?' + qs : ''}`);
  render();
}

async function loadTags() {
  allTags = await apiFetch(`${API}/tags`);
  renderTags();
}

async function refresh() {
  await Promise.all([loadBookmarks(), loadTags()]);
}

// ── Rendering ─────────────────────────────────────────
function render() {
  grid.innerHTML = '';
  const count = allBookmarks.length;
  const noun = count === 1 ? 'bookmark' : 'bookmarks';

  if (activeTag) {
    resultCount.textContent = `${count} ${noun} tagged "${activeTag}"`;
    clearFilterBtn.style.display = 'inline-flex';
  } else if (searchQuery) {
    resultCount.textContent = `${count} ${noun} matching "${searchQuery}"`;
    clearFilterBtn.style.display = 'inline-flex';
  } else {
    resultCount.textContent = `${count} ${noun}`;
    clearFilterBtn.style.display = 'none';
  }

  if (count === 0) {
    emptyState.style.display = 'block';
    emptyMsg.textContent = searchQuery || activeTag
      ? 'No bookmarks match your search.'
      : 'No bookmarks yet. Add your first one!';
    return;
  }

  emptyState.style.display = 'none';
  allBookmarks.forEach(b => grid.appendChild(buildCard(b)));
}

function renderTags() {
  tagsBar.innerHTML = '';
  allTags.forEach(tag => {
    const chip = document.createElement('button');
    chip.className = 'tag-chip' + (activeTag === tag ? ' active' : '');
    chip.textContent = tag;
    chip.addEventListener('click', () => toggleTag(tag));
    tagsBar.appendChild(chip);
  });
}

function buildCard(b) {
  const card = document.createElement('div');
  card.className = 'card';
  card.dataset.id = b.id;

  const domain = getDomain(b.url);
  const initial = (b.title[0] || '?').toUpperCase();
  const tags = parseTags(b.tags);
  const date = formatDate(b.created_at);

  card.innerHTML = `
    <div class="card-top">
      <div class="favicon-placeholder" title="${escHtml(domain)}">${escHtml(initial)}</div>
      <div class="card-title-wrap">
        <a class="card-title" href="${escAttr(b.url)}" target="_blank" rel="noopener noreferrer"
           title="${escAttr(b.title)}">${escHtml(b.title)}</a>
        <div class="card-url">${escHtml(domain)}</div>
      </div>
    </div>
    ${b.description ? `<p class="card-desc">${escHtml(b.description)}</p>` : ''}
    ${tags.length ? `
      <div class="card-tags">
        ${tags.map(t => `<span class="card-tag" data-tag="${escAttr(t)}">${escHtml(t)}</span>`).join('')}
      </div>` : ''}
    <div class="card-footer">
      <span class="card-date">${date}</span>
      <div class="card-actions">
        <button class="icon-btn edit-btn" title="Edit" data-id="${b.id}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </button>
        <button class="icon-btn delete delete-btn" title="Delete" data-id="${b.id}" data-title="${escAttr(b.title)}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            <path d="M10 11v6"/><path d="M14 11v6"/>
            <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
          </svg>
        </button>
      </div>
    </div>
  `;

  card.querySelectorAll('.card-tag').forEach(el => {
    el.addEventListener('click', () => toggleTag(el.dataset.tag));
  });
  card.querySelector('.edit-btn').addEventListener('click', () => openEdit(b.id));
  card.querySelector('.delete-btn').addEventListener('click', e => {
    openDeleteConfirm(e.currentTarget.dataset.id, e.currentTarget.dataset.title);
  });

  return card;
}

// ── Tag filter ────────────────────────────────────────
function toggleTag(tag) {
  activeTag = activeTag === tag ? null : tag;
  renderTags();
  loadBookmarks();
}

// ── Search ────────────────────────────────────────────
let searchTimer;
searchInput.addEventListener('input', () => {
  searchQuery = searchInput.value.trim();
  searchClear.style.display = searchQuery ? 'flex' : 'none';
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadBookmarks, 250);
});

searchClear.addEventListener('click', () => {
  searchInput.value = '';
  searchQuery = '';
  searchClear.style.display = 'none';
  loadBookmarks();
});

clearFilterBtn.addEventListener('click', () => {
  activeTag = null;
  searchQuery = '';
  searchInput.value = '';
  searchClear.style.display = 'none';
  renderTags();
  loadBookmarks();
});

// ── Add / Edit modal ──────────────────────────────────
document.getElementById('addBtn').addEventListener('click', openAdd);
document.getElementById('modalClose').addEventListener('click', closeModal);
document.getElementById('cancelBtn').addEventListener('click', closeModal);
overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });

function openAdd() {
  editId.value = '';
  bookmarkForm.reset();
  clearFormErrors();
  modalTitle.textContent = 'Add Bookmark';
  document.getElementById('saveBtn').textContent = 'Save Bookmark';
  openModal();
}

async function openEdit(id) {
  const b = allBookmarks.find(x => x.id === id);
  if (!b) return;
  clearFormErrors();
  editId.value = b.id;
  urlInput.value = b.url;
  titleInput.value = b.title;
  descInput.value = b.description || '';
  tagsInput.value = b.tags || '';
  modalTitle.textContent = 'Edit Bookmark';
  document.getElementById('saveBtn').textContent = 'Update Bookmark';
  openModal();
}

function openModal()  { overlay.style.display = 'flex'; urlInput.focus(); }
function closeModal() { overlay.style.display = 'none'; }

bookmarkForm.addEventListener('submit', async e => {
  e.preventDefault();
  if (!validateForm()) return;

  const payload = {
    url:         urlInput.value.trim(),
    title:       titleInput.value.trim(),
    description: descInput.value.trim(),
    tags:        normalizeTags(tagsInput.value),
  };

  const id = editId.value;
  try {
    if (id) {
      await apiFetch(`${API}/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Bookmark updated', 'success');
    } else {
      await apiFetch(API, { method: 'POST', body: JSON.stringify(payload) });
      showToast('Bookmark added', 'success');
    }
    closeModal();
    await refresh();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

function validateForm() {
  let valid = true;
  clearFormErrors();

  if (!urlInput.value.trim()) {
    showFieldError(urlInput, urlError, 'URL is required');
    valid = false;
  } else if (!isValidUrl(urlInput.value.trim())) {
    showFieldError(urlInput, urlError, 'Please enter a valid URL');
    valid = false;
  }

  if (!titleInput.value.trim()) {
    showFieldError(titleInput, titleError, 'Title is required');
    valid = false;
  }

  return valid;
}

function showFieldError(input, errEl, msg) {
  input.classList.add('error');
  errEl.textContent = msg;
}

function clearFormErrors() {
  [urlInput, titleInput].forEach(el => el.classList.remove('error'));
  urlError.textContent = '';
  titleError.textContent = '';
}

// ── Delete confirm ────────────────────────────────────
document.getElementById('deleteCancelBtn').addEventListener('click', () => {
  deleteOverlay.style.display = 'none';
  pendingDeleteId = null;
});

deleteOverlay.addEventListener('click', e => {
  if (e.target === deleteOverlay) {
    deleteOverlay.style.display = 'none';
    pendingDeleteId = null;
  }
});

deleteConfirmBtn.addEventListener('click', async () => {
  if (!pendingDeleteId) return;
  try {
    await apiFetch(`${API}/${pendingDeleteId}`, { method: 'DELETE' });
    showToast('Bookmark deleted', 'success');
    deleteOverlay.style.display = 'none';
    pendingDeleteId = null;
    await refresh();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

function openDeleteConfirm(id, title) {
  pendingDeleteId = id;
  deleteTitle.textContent = title;
  deleteOverlay.style.display = 'flex';
}

// ── Toast ─────────────────────────────────────────────
let toastTimer;
function showToast(msg, type = '') {
  toast.textContent = msg;
  toast.className = 'toast show' + (type ? ' ' + type : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.className = 'toast'; }, 2800);
}

// ── Utils ─────────────────────────────────────────────
function getDomain(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); }
  catch { return url; }
}

function parseTags(str) {
  if (!str) return [];
  return str.split(',').map(t => t.trim()).filter(Boolean);
}

function normalizeTags(str) {
  return parseTags(str).join(', ');
}

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function isValidUrl(str) {
  try { new URL(str); return true; } catch { return false; }
}

function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escAttr(str) { return escHtml(str); }

// ── Init ──────────────────────────────────────────────
refresh();
