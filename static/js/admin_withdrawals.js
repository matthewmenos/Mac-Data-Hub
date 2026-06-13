async function updateWithdrawal(id, status) {
  const resp = await fetch('/admin/withdrawals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, status }),
  });
  if (resp.ok) location.reload();
}

document.querySelectorAll('.mark-paid-btn').forEach(btn => {
  btn.addEventListener('click', () => updateWithdrawal(btn.dataset.id, 'paid'));
});
document.querySelectorAll('.mark-failed-btn').forEach(btn => {
  btn.addEventListener('click', () => updateWithdrawal(btn.dataset.id, 'failed'));
});
