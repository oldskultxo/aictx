(function () {
  var targets = document.querySelectorAll('.js-github-stars');
  if (!targets.length) return;

  var cacheKey = 'aictx.github.stars';
  var cacheTtlMs = 6 * 60 * 60 * 1000;

  function render(count) {
    var formatted = Number(count).toLocaleString();
    targets.forEach(function (target) {
      var countNode = target.querySelector('.js-github-stars-count');
      if (!countNode) return;
      countNode.textContent = formatted;
      target.setAttribute('aria-label', formatted + ' GitHub stars');
      target.classList.add('is-visible');
    });
  }

  function readCache() {
    try {
      var cached = JSON.parse(localStorage.getItem(cacheKey) || 'null');
      if (!cached || typeof cached.count !== 'number') return null;
      if (Date.now() - cached.timestamp > cacheTtlMs) return null;
      return cached.count;
    } catch (error) {
      return null;
    }
  }

  function writeCache(count) {
    try {
      localStorage.setItem(cacheKey, JSON.stringify({ count: count, timestamp: Date.now() }));
    } catch (error) {}
  }

  var cachedCount = readCache();
  if (cachedCount !== null) render(cachedCount);

  fetch('https://api.github.com/repos/oldskultxo/aictx', { headers: { Accept: 'application/vnd.github+json' } })
    .then(function (response) { return response.ok ? response.json() : null; })
    .then(function (data) {
      if (!data || typeof data.stargazers_count !== 'number') return;
      writeCache(data.stargazers_count);
      render(data.stargazers_count);
    })
    .catch(function () {});
}());
