async function approveWithdrawal(id, btn) {
  if (!confirm('Approve and send payment via Paystack?')) return;
  btn.disabled = true;
  btn.textContent = 'Sending…';
  try {
    const resp = await fetch('/admin/withdrawals', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify({ id, status: 'approved' }),
    });
    
    // Handle 401 Unauthorized (session expired)
    if (resp.status === 401) {
      alert('Session expired. Please refresh the page and log in again.');
      location.reload();
      return;
    }
    
    // Check if response is JSON
    const contentType = resp.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      const text = await resp.text();
      if (text.includes('<!DOCTYPE') || text.includes('<html')) {
        alert('Server error. Please try again or check the logs.');
        btn.disabled = false;
        btn.textContent = 'Approve & Pay';
        return;
      }
      throw new Error('Invalid response from server');
    }
    
    const data = await resp.json();
    if (resp.ok && data.ok) {
      location.reload();
    } else {
      const errMsg = data.error || 'Unknown error';
      // Check for specific Paystack error messages
      if (errMsg.includes('insufficient balance') || errMsg.includes('insufficient funds')) {
        alert('Paystack wallet balance is insufficient. Please fund your Paystack wallet and try again.');
      } else {
        alert('Transfer failed: ' + errMsg);
      }
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
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify({ id, status: 'failed' }),
    });
    
    // Handle 401 Unauthorized (session expired)
    if (resp.status === 401) {
      alert('Session expired. Please refresh the page and log in again.');
      location.reload();
      return;
    }
    
    // Check if response is JSON
    const contentType = resp.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      const text = await resp.text();
      if (text.includes('<!DOCTYPE') || text.includes('<html')) {
        alert('Server error. Please try again or check the logs.');
        return;
      }
      throw new Error('Invalid response from server');
    }
    
    const data = await resp.json();
    if (resp.ok && data.ok) {
      location.reload();
    } else {
      alert('Failed to reject withdrawal: ' + (data.error || 'Unknown error'));
    }
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
