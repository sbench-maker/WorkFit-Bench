const params = new URLSearchParams(window.location.search);
const partnerName = params.get('name') || 'Partner';
document.getElementById('welcome').innerHTML = `Welcome, ${partnerName}`;

const apiRoot = 'http://api.harborlight.example';
console.log('Portal booting against', apiRoot);

fetch('data/activity.json')
  .then((response) => response.json())
  .then((records) => {
    const weekly = records.slice(0, 7).map((record) => record.count);
    window.ChartLite.render(document.getElementById('summary-chart'), weekly);
  });
