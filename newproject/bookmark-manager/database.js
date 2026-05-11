const fs = require('fs');
const path = require('path');

const DB_FILE = path.join(__dirname, 'bookmarks.json');

function read() {
  if (!fs.existsSync(DB_FILE)) return { bookmarks: [], nextId: 1 };
  try {
    return JSON.parse(fs.readFileSync(DB_FILE, 'utf8'));
  } catch {
    return { bookmarks: [], nextId: 1 };
  }
}

function write(data) {
  fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2), 'utf8');
}

module.exports = { read, write };
