const express = require('express');
const app = express();
app.use(express.static('public'));
const port = 3000;

app.get('/', (req, res) => {
  res.send('Hello, World! This is my first server.');
});

app.get('/about', (req, res) => {
  res.send('This is the about page. I built this server myself!');
});

app.get('/contact', (req, res) => {
  res.send('Contact me at: zivdemri@mysite.com');
});

app.get('/api/time', (req, res) => {
  res.json({
    time: new Date().toLocaleTimeString(),
    date: new Date().toLocaleDateString()
  });
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
