// ── Payout profile form ──────────────────────────────────────────────────────

function showPayoutForm() {
  const wrap = document.getElementById('payout-form-wrap');
  if (wrap) wrap.classList.remove('hidden');
}

(function () {
  const form      = document.getElementById('payout-form');
  if (!form) return;
  const errEl     = document.getElementById('payout-error');
  const successEl = document.getElementById('payout-success');
  const btn       = document.getElementById('payout-btn');

  form.addEventListener('submit', async e => {
    e.preventDefault();
    errEl.classList.add('hidden');
    successEl.classList.add('hidden');

    const phone   = document.getElementById('payout-phone').value.trim();
    const name    = document.getElementById('payout-name').value.trim();
    const network = document.getElementById('payout-network').value;

    if (!phone || !name || !network) {
      errEl.textContent = 'All fields are required.';
      errEl.classList.remove('hidden');
      return;
    }

    btn.disabled = true;
    btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="animation:spin .7s linear infinite"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-.49-5"/></svg> Saving…';

    try {
      const resp = await fetch('/dashboard/wallet/setup-payout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, account_name: name, network }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Something went wrong.');
      successEl.textContent = 'Payout profile saved! Withdrawals will go to this account.';
      successEl.classList.remove('hidden');
      setTimeout(() => location.reload(), 1500);
    } catch (err) {
      errEl.textContent = err.message;
      errEl.classList.remove('hidden');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg> Save Payout Profile';
    }
  });
})();

// ── Withdrawal form ──────────────────────────────────────────────────────────

(function () {
  const form      = document.getElementById('withdraw-form');
  if (!form) return;
  const errEl     = document.getElementById('withdraw-error');
  const successEl = document.getElementById('withdraw-success');
  const wdBtn     = document.getElementById('withdraw-btn');

  form.addEventListener('submit', async e => {
    e.preventDefault();
    errEl.classList.add('hidden');
    successEl.classList.add('hidden');

    const ghs = parseFloat(document.getElementById('amount').value) || 0;
    if (ghs <= 0) {
      errEl.textContent = 'Enter a valid amount.';
      errEl.classList.remove('hidden');
      return;
    }

    wdBtn.disabled = true;
    wdBtn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="animation:spin .7s linear infinite"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-.49-5"/></svg> Sending…';

    try {
      const resp = await fetch('/dashboard/wallet/withdraw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount: ghs }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Something went wrong.');
      successEl.textContent = data.message || 'Transfer initiated. Funds will arrive shortly.';
      successEl.classList.remove('hidden');
      form.reset();
      setTimeout(() => location.reload(), 2500);
    } catch (err) {
      errEl.textContent = err.message;
      errEl.classList.remove('hidden');
    } finally {
      wdBtn.disabled = false;
      wdBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/></svg> Withdraw now';
    }
  });
})();
