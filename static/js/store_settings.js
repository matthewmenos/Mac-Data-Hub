const form      = document.getElementById('store-form');
const errEl     = document.getElementById('store-error');
const successEl = document.getElementById('store-success');

form.addEventListener('submit', async e => {
  e.preventDefault();
  errEl.classList.add('hidden');
  successEl.classList.add('hidden');

  try {
    const resp = await fetch('/dashboard/store', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        store_name:  document.getElementById('store_name').value.trim(),
        description: document.getElementById('description').value.trim(),
      }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Failed to save.');
    successEl.textContent = 'Store settings saved.';
    successEl.classList.remove('hidden');
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  }
});

function copyStoreUrl() {
  const inp = document.getElementById('store-url');
  inp.select();
  navigator.clipboard.writeText(inp.value).catch(() => document.execCommand('copy'));
}
