(function () {
  const form     = document.getElementById('track-form');
  const phoneEl  = document.getElementById('track-phone');
  const trackBtn = document.getElementById('track-btn');
  const errEl    = document.getElementById('track-error');
  const modal    = document.getElementById('track-modal');
  const backdrop = document.getElementById('track-modal-backdrop');
  const closeBtn = document.getElementById('track-modal-close');
  const subEl    = document.getElementById('track-modal-sub');
  const results  = document.getElementById('track-results');

  if (!form) return;

  const STATUS_LABELS = {
    pending:    { label: 'Pending',    cls: 'status-pending'    },
    paid:       { label: 'Paid',       cls: 'status-pending'    },
    dispatched: { label: 'Delivered',  cls: 'status-dispatched' },
    failed:     { label: 'Failed',     cls: 'status-failed'     },
  };

  function fmtDate(iso) {
    const d = new Date(iso.replace(' ', 'T'));
    return d.toLocaleDateString('en-GH', { day: 'numeric', month: 'short', year: 'numeric' })
      + ' ' + d.toLocaleTimeString('en-GH', { hour: '2-digit', minute: '2-digit' });
  }

  function fmtVol(mb) {
    return mb >= 1000 ? (mb / 1000).toFixed(mb % 1000 === 0 ? 0 : 1) + 'GB' : mb + 'MB';
  }

  function renderOrders(orders, phone) {
    subEl.textContent = `Showing orders for ${phone}`;
    if (!orders.length) {
      results.innerHTML = `
        <div class="track-empty">
          <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <div>No orders found for <strong>${phone}</strong>.</div>
          <div style="font-size:.8rem;margin-top:.3rem">Make sure you enter the exact number used during checkout.</div>
        </div>`;
      return;
    }
    results.innerHTML = orders.map(o => {
      const st  = STATUS_LABELS[o.status] || { label: o.status, cls: 'status-pending' };
      const net = (o.network || '').toLowerCase();
      const amt = 'GHS ' + (o.amount_pesewas / 100).toFixed(2);
      return `
        <div class="track-order-item">
          <div class="track-order-net net-${net}">${o.network ? o.network.toUpperCase().slice(0,3) : '?'}</div>
          <div class="track-order-info">
            <div class="track-order-label">${o.label || fmtVol(o.volume_mb)}</div>
            <div class="track-order-meta">
              <span class="status-pill ${st.cls}" style="font-size:.7rem;padding:.2rem .55rem">${st.label}</span>
            </div>
          </div>
          <div class="track-order-right">
            <div class="track-order-amount">${amt}</div>
            <div class="track-order-date">${fmtDate(o.created_at)}</div>
          </div>
        </div>`;
    }).join('');
  }

  function openModal() {
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    modal.classList.add('hidden');
    document.body.style.overflow = '';
  }

  closeBtn.addEventListener('click', closeModal);
  backdrop.addEventListener('click', closeModal);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    errEl.classList.add('hidden');
    const phone = phoneEl.value.trim();
    if (!phone) {
      errEl.textContent = 'Please enter a phone number.';
      errEl.classList.remove('hidden');
      return;
    }

    trackBtn.disabled = true;
    trackBtn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="animation:spin .7s linear infinite"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-.49-5"/></svg> Searching…';

    try {
      const storeId = window.TRACK_STORE_ID;
      const url = '/track?phone=' + encodeURIComponent(phone) +
        (storeId ? '&store_id=' + encodeURIComponent(storeId) : '');
      const resp = await fetch(url);
      const data = await resp.json();
      if (!resp.ok || !data.ok) throw new Error(data.error || 'Could not fetch orders.');
      renderOrders(data.orders, phone);
      openModal();
    } catch (err) {
      errEl.textContent = err.message;
      errEl.classList.remove('hidden');
    } finally {
      trackBtn.disabled = false;
      trackBtn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Track';
    }
  });
})();
