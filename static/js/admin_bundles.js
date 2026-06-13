const modal      = document.getElementById('bundle-modal');
const modalTitle = document.getElementById('modal-title');
const form       = document.getElementById('bundle-form');
const errEl      = document.getElementById('bundle-error');
let editing      = false;

function openModal() { modal.classList.remove('hidden'); }
function closeModal() { modal.classList.add('hidden'); }

document.getElementById('add-bundle-btn')?.addEventListener('click', () => {
  editing = false;
  modalTitle.textContent = 'Add bundle';
  form.reset();
  document.getElementById('bundle-id').value = '';
  openModal();
});
document.getElementById('add-bundle-btn-empty')?.addEventListener('click', () => {
  editing = false;
  modalTitle.textContent = 'Add bundle';
  form.reset();
  document.getElementById('bundle-id').value = '';
  openModal();
});

document.getElementById('cancel-modal')?.addEventListener('click', closeModal);
document.getElementById('cancel-modal-2')?.addEventListener('click', closeModal);
document.getElementById('modal-backdrop')?.addEventListener('click', closeModal);

document.querySelectorAll('.edit-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    editing = true;
    modalTitle.textContent = 'Edit bundle';
    const b = JSON.parse(btn.dataset.bundle);
    document.getElementById('bundle-id').value    = b.id;
    document.getElementById('b-network').value    = b.network;
    document.getElementById('b-offer-slug').value = b.offer_slug;
    document.getElementById('b-label').value      = b.label;
    document.getElementById('b-volume').value     = (b.volume_mb / 1000).toFixed(2).replace(/\.?0+$/, '');
    document.getElementById('b-validity').value   = b.validity_days;
    document.getElementById('b-price').value        = (b.base_price_pesewas / 100).toFixed(2);
    document.getElementById('b-guest-price').value  = ((b.guest_price_pesewas || b.base_price_pesewas) / 100).toFixed(2);
    document.getElementById('b-active').value       = b.is_active ? '1' : '0';
    openModal();
  });
});

document.querySelectorAll('.delete-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    if (!confirm('Delete this bundle? Resellers using it will lose their pricing.')) return;
    const resp = await fetch('/admin/bundles', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: btn.dataset.id }),
    });
    if (resp.ok) location.reload();
  });
});

form.addEventListener('submit', async e => {
  e.preventDefault();
  errEl.classList.add('hidden');
  const saveBtn = document.getElementById('save-bundle-btn');
  saveBtn.disabled = true;
  saveBtn.textContent = 'Saving…';

  const ghsValue      = parseFloat(document.getElementById('b-price').value) || 0;
  const guestGhs      = parseFloat(document.getElementById('b-guest-price').value) || 0;
  const gbValue       = parseFloat(document.getElementById('b-volume').value) || 0;

  const payload = {
    id:                   document.getElementById('bundle-id').value,
    network:              document.getElementById('b-network').value,
    offer_slug:           document.getElementById('b-offer-slug').value.trim(),
    label:                document.getElementById('b-label').value.trim(),
    volume_mb:            Math.round(gbValue * 1000),
    validity_days:        parseInt(document.getElementById('b-validity').value),
    base_price_pesewas:   Math.round(ghsValue * 100),
    guest_price_pesewas:  Math.round(guestGhs * 100),
    is_active:            parseInt(document.getElementById('b-active').value),
  };

  const resp = await fetch('/admin/bundles', {
    method: editing ? 'PUT' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  if (!resp.ok) {
    errEl.textContent = data.error || 'Failed to save.';
    errEl.classList.remove('hidden');
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save bundle';
    return;
  }
  location.reload();
});
