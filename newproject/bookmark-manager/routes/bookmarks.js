const express = require('express');
const router = express.Router();
const { read, write } = require('../database');

function now() {
  return new Date().toISOString();
}

function matchesTag(bookmark, tag) {
  const tags = bookmark.tags.split(',').map(t => t.trim()).filter(Boolean);
  return tags.includes(tag);
}

router.get('/tags', (req, res) => {
  const { bookmarks } = read();
  const tagSet = new Set();
  bookmarks.forEach(b => {
    b.tags.split(',').map(t => t.trim()).filter(Boolean).forEach(t => tagSet.add(t));
  });
  res.json([...tagSet].sort());
});

router.get('/', (req, res) => {
  const { search, tag } = req.query;
  let { bookmarks } = read();

  if (search) {
    const q = search.toLowerCase();
    bookmarks = bookmarks.filter(b =>
      b.title.toLowerCase().includes(q) ||
      b.url.toLowerCase().includes(q) ||
      (b.description || '').toLowerCase().includes(q) ||
      (b.tags || '').toLowerCase().includes(q)
    );
  }

  if (tag) {
    bookmarks = bookmarks.filter(b => matchesTag(b, tag));
  }

  bookmarks.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  res.json(bookmarks);
});

router.post('/', (req, res) => {
  const { url, title, description, tags } = req.body;
  if (!url || !title) return res.status(400).json({ error: 'URL and title are required' });

  const db = read();
  const bookmark = {
    id: db.nextId++,
    url,
    title,
    description: description || '',
    tags: tags || '',
    created_at: now(),
    updated_at: now(),
  };
  db.bookmarks.push(bookmark);
  write(db);
  res.status(201).json(bookmark);
});

router.put('/:id', (req, res) => {
  const { url, title, description, tags } = req.body;
  if (!url || !title) return res.status(400).json({ error: 'URL and title are required' });

  const id = parseInt(req.params.id, 10);
  const db = read();
  const idx = db.bookmarks.findIndex(b => b.id === id);
  if (idx === -1) return res.status(404).json({ error: 'Bookmark not found' });

  db.bookmarks[idx] = {
    ...db.bookmarks[idx],
    url,
    title,
    description: description || '',
    tags: tags || '',
    updated_at: now(),
  };
  write(db);
  res.json(db.bookmarks[idx]);
});

router.delete('/:id', (req, res) => {
  const id = parseInt(req.params.id, 10);
  const db = read();
  const idx = db.bookmarks.findIndex(b => b.id === id);
  if (idx === -1) return res.status(404).json({ error: 'Bookmark not found' });

  db.bookmarks.splice(idx, 1);
  write(db);
  res.json({ success: true });
});

module.exports = router;
