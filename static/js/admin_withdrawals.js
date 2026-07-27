async function approveWithdrawal(id, btn) {
  if (!confirm('Approve and send payment via Paystack?')) return;
  btn.disabled = true;
  btn.textContent = 'Sending…';
  try {
    const resp = await fetch('/admin/withdrawals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, status: 'approved' }),
    });
    
    // Check if response is JSON
    const contentType = resp.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      const text = await resp.text();
      if (text.includes('<!DOCTYPE') || text.includes('<html')) {
        alert('Session expired. Please refresh the page and log in again.');
        location.reload();
        return;
      }
      throw new Error('Invalid response from server');
    }
    
    const data = await resp.json();
    if (resp.ok && data.ok) {
      location.reload();
    } else {
      alert('Transfer failed: ' + (data.error || 'Unknown error'));
      btn.disabled = false;
      btn.textContent = 'Approve & Pay';
    }
  } catch (e) {
    alert('Error: ' + e.message);
    btn.disabled = false;
    btn.textContent = 'Approve & Pay';
  }
}

async function rejectWithdrawal(id) {
  if (!confirm('Reject this withdrawal and refund the reseller?')) return;
  try {
    const resp = await fetch('/admin/withdrawals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, status: 'failed' }),
    });
    
    // Check if response is JSON
    const contentType = resp.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      const text = await resp.text();
      if (text.includes('<!DOCTYPE') || text.includes('<html')) {
        alert('Session expired. Please refresh the page and log in again.');
        location.reload();
        return;
      }
      throw new Error('Invalid response from server');
    }
    
    if (resp.ok) location.reload();
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

document.querySelectorAll('.approve-btn').forEach(btn => {
  btn.addEventListener('click', () => approveWithdrawal(btn.dataset.id, btn));
});
document.querySelectorAll('.mark-failed-btn').forEach(btn => {
  btn.addEventListener('click', () => rejectWithdrawal(btn.dataset.id));
});
