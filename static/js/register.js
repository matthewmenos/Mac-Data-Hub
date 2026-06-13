const form    = document.getElementById('register-form');
const errEl   = document.getElementById('form-error');
const regBtn  = document.getElementById('register-btn');

form.addEventListener('submit', async e => {
  e.preventDefault();
  errEl.classList.add('hidden');

  const password = document.getElementById('password').value;
  const confirm  = document.getElementById('confirm_password').value;
  if (password !== confirm) {
    errEl.textContent = 'Passwords do not match.';
    errEl.classList.remove('hidden');
    return;
  }

  const slug = document.getElementById('slug').value.trim();
  if (!/^[a-z0-9-]+$/.test(slug)) {
    errEl.textContent = 'Store URL can only contain lowercase letters, numbers and hyphens.';
    errEl.classList.remove('hidden');
    return;
  }

  regBtn.disabled = true;
  regBtn.textContent = 'Please wait…';

  try {
    const resp = await fetch('/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        full_name: document.getElementById('full_name').value.trim(),
        phone:     document.getElementById('phone').value.trim(),
        email:     document.getElementById('email').value.trim(),
        slug,
        password,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) { throw new Error(data.error || 'Something went wrong.'); }
    window.location.href = data.authorization_url;
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
    regBtn.disabled = false;
    regBtn.textContent = 'Try again';
  }
});
