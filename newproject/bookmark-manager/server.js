const express = require('express');
const path = require('path');
const bookmarksRouter = require('./routes/bookmarks');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));
app.use('/api/bookmarks', bookmarksRouter);

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Bookmark Manager running on http://localhost:${PORT}`);
});
