const tabs  = document.querySelectorAll('.tab');
const cards = document.querySelectorAll('.bundle-card');

function filterNet(net) {
  tabs.forEach(t => t.classList.toggle('active', t.dataset.net === net));
  cards.forEach(c => { c.style.display = (net === 'all' || c.dataset.net === net) ? '' : 'none'; });
}

tabs.forEach(tab => {
  tab.addEventListener('click', () => filterNet(tab.dataset.net));
});

// Pre-filter from URL param e.g. /?net=mtn
const param = new URLSearchParams(location.search).get('net');
if (param) filterNet(param);
