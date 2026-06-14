/* ── Store details form ──────────────────────────────────── */
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

/* ── Logo upload ─────────────────────────────────────────── */
(function () {
  const fileInput   = document.getElementById('logo-file-input');
  const previewImg  = document.getElementById('logo-preview-img');
  const placeholder = document.getElementById('logo-preview-placeholder');
  const logoErr     = document.getElementById('logo-error');
  const logoOk      = document.getElementById('logo-success');
  const removeBtn   = document.getElementById('logo-remove-btn');

  if (!fileInput) return;

  fileInput.addEventListener('change', async function () {
    const file = this.files[0];
    if (!file) return;

    logoErr.classList.add('hidden');
    logoOk.classList.add('hidden');

    if (file.size > 2 * 1024 * 1024) {
      logoErr.textContent = 'Image must be under 2 MB.';
      logoErr.classList.remove('hidden');
      this.value = '';
      return;
    }

    // Local preview
    const reader = new FileReader();
    reader.onload = function (ev) {
      previewImg.src = ev.target.result;
      previewImg.classList.remove('hidden');
      if (placeholder) placeholder.classList.add('hidden');
    };
    reader.readAsDataURL(file);

    // Upload
    const fd = new FormData();
    fd.append('logo', file);

    try {
      const resp = await fetch('/dashboard/store/logo', { method: 'POST', body: fd });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Upload failed.');
      logoOk.textContent = 'Logo updated.';
      logoOk.classList.remove('hidden');
      // Show remove button if not already present
      if (!removeBtn) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.id   = 'logo-remove-btn';
        btn.className = 'btn btn-ghost btn-sm';
        btn.style.cssText = 'color:var(--red);margin-top:.5rem;';
        btn.textContent = 'Remove logo';
        btn.addEventListener('click', removeLogo);
        logoOk.after(btn);
      }
    } catch (err) {
      logoErr.textContent = err.message;
      logoErr.classList.remove('hidden');
    }
  });

  async function removeLogo() {
    logoErr.classList.add('hidden');
    logoOk.classList.add('hidden');
    try {
      const resp = await fetch('/dashboard/store/logo/remove', { method: 'POST' });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Failed to remove logo.');
      previewImg.src = '';
      previewImg.classList.add('hidden');
      if (placeholder) placeholder.classList.remove('hidden');
      if (removeBtn) removeBtn.remove();
      logoOk.textContent = 'Logo removed.';
      logoOk.classList.remove('hidden');
    } catch (err) {
      logoErr.textContent = err.message;
      logoErr.classList.remove('hidden');
    }
  }

  if (removeBtn) removeBtn.addEventListener('click', removeLogo);
})();
