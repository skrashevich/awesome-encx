const statusEl = document.getElementById('status');
const contentEl = document.getElementById('content');
const searchInput = document.getElementById('search-input');
const resultCount = document.getElementById('result-count');
const repoLink = document.getElementById('repo-link');
const rawLink = document.getElementById('raw-link');

const segments = window.location.pathname.split('/').filter(Boolean);
const repoName = segments.length ? segments[0] : 'awesome-encx';
const owner = 'skrashevich';
const defaultBranch = 'main';
const githubRepoUrl = `https://github.com/${owner}/${repoName}`;
const rawReadmeUrl = `https://raw.githubusercontent.com/${owner}/${repoName}/${defaultBranch}/README.md`;

repoLink.href = githubRepoUrl;
rawLink.href = rawReadmeUrl;

const repoBlocks = [];

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.style.color = isError ? '#ffb4b4' : '';
}

function registerRepoBlocks() {
  repoBlocks.length = 0;
  const headings = [...contentEl.querySelectorAll('h3')];
  headings.forEach((h3) => {
    const block = [h3];
    let node = h3.nextElementSibling;
    while (node && node.tagName !== 'H3' && node.tagName !== 'H2') {
      block.push(node);
      node = node.nextElementSibling;
    }
    repoBlocks.push(block);
  });
}

function applyFilter(query) {
  const needle = query.trim().toLowerCase();
  let visible = 0;

  if (!needle) {
    repoBlocks.forEach((block) => block.forEach((n) => n.classList.remove('hidden-by-filter')));
    visible = repoBlocks.length;
  } else {
    repoBlocks.forEach((block) => {
      const text = block.map((n) => n.textContent || '').join(' ').toLowerCase();
      const isMatch = text.includes(needle);
      block.forEach((n) => n.classList.toggle('hidden-by-filter', !isMatch));
      if (isMatch) visible += 1;
    });
  }

  resultCount.textContent = `Показано: ${visible} / ${repoBlocks.length}`;

  const sections = [...contentEl.querySelectorAll('h2')];
  sections.forEach((h2) => {
    let node = h2.nextElementSibling;
    let hasVisible = false;
    while (node && node.tagName !== 'H2') {
      if (node.tagName === 'H3' && !node.classList.contains('hidden-by-filter')) {
        hasVisible = true;
      }
      node = node.nextElementSibling;
    }
    h2.classList.toggle('hidden-by-filter', !hasVisible && !!needle);
  });
}

async function loadReadme() {
  try {
    setStatus('Загружаю список…');
    const response = await fetch(rawReadmeUrl, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const markdown = await response.text();

    contentEl.innerHTML = marked.parse(markdown);
    registerRepoBlocks();
    applyFilter('');

    statusEl.hidden = true;
    contentEl.hidden = false;
  } catch (error) {
    setStatus(`Не удалось загрузить README: ${error.message}`, true);
  }
}

searchInput.addEventListener('input', (event) => applyFilter(event.target.value));

loadReadme();
