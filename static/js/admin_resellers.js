document.querySelectorAll('.toggle-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    const resp = await fetch(`/admin/resellers/${btn.dataset.id}/toggle`, { method: 'POST' });
    const data = await resp.json();
    if (data.ok) location.reload();
  });
});
