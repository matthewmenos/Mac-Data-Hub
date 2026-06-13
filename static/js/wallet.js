const form      = document.getElementById('withdraw-form');
const errEl     = document.getElementById('withdraw-error');
const successEl = document.getElementById('withdraw-success');
const wdBtn     = document.getElementById('withdraw-btn');

form.addEventListener('submit', async e => {
  e.preventDefault();
  errEl.classList.add('hidden');
  successEl.classList.add('hidden');

  const ghs    = parseFloat(document.getElementById('amount').value) || 0;
  const mobile = document.getElementById('mobile_number').value.trim();
  const net    = document.getElementById('network').value;

  if (ghs <= 0) { errEl.textContent = 'Enter a valid amount.'; errEl.classList.remove('hidden'); return; }

  wdBtn.disabled = true;
  wdBtn.textContent = 'Submitting…';

  try {
    const resp = await fetch('/dashboard/wallet/withdraw', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount: ghs, mobile_number: mobile, network: net }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Something went wrong.');
    successEl.textContent = 'Withdrawal request submitted. Funds will be sent to your mobile money shortly.';
    successEl.classList.remove('hidden');
    form.reset();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  } finally {
    wdBtn.disabled = false;
    wdBtn.textContent = 'Request withdrawal';
  }
});
