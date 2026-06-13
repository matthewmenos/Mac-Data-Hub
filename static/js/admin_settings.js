const form      = document.getElementById('settings-form');
const errEl     = document.getElementById('settings-error');
const successEl = document.getElementById('settings-success');

form.addEventListener('submit', async e => {
  e.preventDefault();
  errEl.classList.add('hidden');
  successEl.classList.add('hidden');

  const payload = {};
  new FormData(form).forEach((v, k) => { payload[k] = v; });

  try {
    const resp = await fetch('/admin/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Failed.');
    successEl.textContent = 'Settings saved.';
    successEl.classList.remove('hidden');
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  }
});
