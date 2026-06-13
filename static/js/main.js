// Global utilities

function toggleNav() {
  const nav = document.getElementById('nav-links');
  if (nav) nav.classList.toggle('open');
}

async function postJSON(url, body) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await resp.json().catch(() => ({}));
  return { ok: resp.ok, data };
}

// Auto-dismiss flash messages
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => el.remove(), 5000);
});
