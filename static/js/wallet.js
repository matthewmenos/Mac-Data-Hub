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

  // ── Auto-resolve account name ─────────────────────────────────────────────
  const phoneEl    = document.getElementById('payout-phone');
  const networkEl  = document.getElementById('payout-network');
  const nameEl     = document.getElementById('payout-name');
  const statusEl   = document.getElementById('resolve-status');
  const nameHint   = document.getElementById('name-hint');
  let resolveTimer = null;

  function setNameEditable(editable) {
    nameEl.readOnly = !editable;
    nameEl.style.background = editable ? '' : 'var(--surface-alt,#f3f4f6)';
    nameEl.style.color      = editable ? '' : 'var(--muted,#6b7280)';
    nameEl.style.cursor     = editable ? '' : 'default';
  }

  function setResolveStatus(msg, type) {
    if (!statusEl) return;
    statusEl.textContent = msg;
    statusEl.style.display = msg ? '' : 'none';
    statusEl.style.color = type === 'ok'      ? 'var(--green)'
                         : type === 'loading' ? 'var(--muted,#6b7280)'
                         : '#ef4444';
  }

  async function tryResolve() {
    const number  = phoneEl.value.trim();
    const network = networkEl.value;
    if (number.length < 10 || !network) return;
    setResolveStatus('Looking up account name…', 'loading');
    nameEl.value = '';
    setNameEditable(false);
    if (nameHint) nameHint.style.display = '';
    try {
      const resp = await fetch(
        `/dashboard/wallet/resolve-account?number=${encodeURIComponent(number)}&network=${encodeURIComponent(network)}`
      );
      const data = await resp.json();
      if (data.ok && data.name) {
        nameEl.value = data.name;
        setNameEditable(false);
        setResolveStatus('✓ Verified by Paystack', 'ok');
        if (nameHint) nameHint.style.display = 'none';
      } else {
        setNameEditable(true);
        nameEl.focus();
        setResolveStatus('Could not verify — enter your name manually.', 'err');
        if (nameHint) nameHint.style.display = 'none';
      }
    } catch {
      setNameEditable(true);
      nameEl.focus();
      setResolveStatus('Could not verify — enter your name manually.', 'err');
      if (nameHint) nameHint.style.display = 'none';
    }
  }

  function scheduleResolve() {
    // Reset name field whenever number or network changes
    nameEl.value = '';
    setNameEditable(false);
    setResolveStatus('', '');
    if (nameHint) nameHint.style.display = '';
    clearTimeout(resolveTimer);
    resolveTimer = setTimeout(tryResolve, 700);
  }

  if (phoneEl)   phoneEl.addEventListener('input', scheduleResolve);
  if (networkEl) networkEl.addEventListener('change', scheduleResolve);

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
  const amountEl  = document.getElementById('amount');
  const feePctEl  = document.getElementById('wd-fee-pct');
  const feePreview  = document.getElementById('wd-fee-preview');
  const feeAmountEl = document.getElementById('wd-fee-amount');
  const payoutEl    = document.getElementById('wd-payout-amount');

  const feePct = feePctEl ? parseFloat(feePctEl.value) || 0 : 0;

  function updateFeePreview() {
    if (!feePreview || feePct <= 0) return;
    const ghs = parseFloat(amountEl.value) || 0;
    if (ghs <= 0) { feePreview.classList.add('hidden'); return; }
    const fee    = Math.round(ghs * 100 * feePct / 100) / 100;
    const payout = Math.max(0, ghs - fee);
    feeAmountEl.textContent = 'GHS ' + fee.toFixed(2);
    payoutEl.textContent    = 'GHS ' + payout.toFixed(2);
    feePreview.classList.remove('hidden');
  }

  if (amountEl) amountEl.addEventListener('input', updateFeePreview);

  form.addEventListener('submit', async e => {
    e.preventDefault();
    errEl.classList.add('hidden');
    successEl.classList.add('hidden');

    const ghs = parseFloat(amountEl.value) || 0;
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
      if (feePreview) feePreview.classList.add('hidden');
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
