const form    = document.getElementById('checkout-form');
const errEl   = document.getElementById('form-error');
const payBtn  = document.getElementById('pay-btn');
const bundleId = document.getElementById('bundle-id').value;
const storeId  = document.getElementById('store-id').value;

form.addEventListener('submit', async e => {
  e.preventDefault();
  errEl.classList.add('hidden');
  const phone = document.getElementById('phone').value.trim();
  const email = document.getElementById('email').value.trim();

  if (!/^0[235]\d{8}$/.test(phone)) {
    errEl.textContent = 'Enter a valid 10-digit Ghana mobile number.';
    errEl.classList.remove('hidden');
    return;
  }

  payBtn.disabled = true;
  payBtn.textContent = 'Please wait…';

  try {
    const resp = await fetch('/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bundle_id: bundleId, store_id: storeId || null, phone, email }),
    });
    const data = await resp.json();
    if (!resp.ok) { throw new Error(data.error || 'Something went wrong.'); }
    window.location.href = data.authorization_url;
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
    payBtn.disabled = false;
    payBtn.textContent = 'Try again';
  }
});
