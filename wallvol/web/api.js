// Shared by index.html, setup.html and unlock.html.
// Every /api call carries the per-launch token the server put in this page (it
// refuses calls without it), and state changes are JSON (see server.py)
const TOKEN = (document.querySelector('meta[name="wallvol-token"]') || {}).content || '';
{
  const plainFetch = window.fetch.bind(window);
  window.fetch = (url, opts = {}) => {
    if (typeof url === 'string' && url.startsWith('/api/')) {
      const headers = new Headers(opts.headers || {});
      headers.set('X-Wallvol-Token', TOKEN);
      const method = (opts.method || 'GET').toUpperCase();
      if (method !== 'GET' && method !== 'HEAD') {
        headers.set('Content-Type', 'application/json');
        if (opts.body === undefined) opts = { ...opts, body: '{}' };
      }
      opts = { ...opts, headers };
    }
    return plainFetch(url, opts);
  };
}
