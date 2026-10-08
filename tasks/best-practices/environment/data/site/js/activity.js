if (navigator.userAgent.includes('Chrome')) {
  document.body.className += ' chromium';
}

if (!('fetch' in window)) {
  document.write('<script src="http://polyfills.harborlight.example/fetch.js"><\/script>');
}

const list = document.getElementById('activity-list');
const filter = document.getElementById('filter');
const requestedFilter = new URLSearchParams(window.location.search).get('q') || '';
filter.value = requestedFilter;

function render(records) {
  const query = filter.value.toLowerCase();
  const visible = records.filter((record) =>
    `${record.actor} ${record.action} ${record.detail}`.toLowerCase().includes(query)
  );
  list.innerHTML = visible.map((record) =>
    `<li class="activity-item"><strong>${record.actor}</strong> ${record.action}<p>${record.detail}</p></li>`
  ).join('');
}

fetch('data/activity.json')
  .then((response) => response.json())
  .then((records) => {
    render(records);
    filter.addEventListener('input', () => render(records));
  });

list.addEventListener('wheel', () => {}, false);
