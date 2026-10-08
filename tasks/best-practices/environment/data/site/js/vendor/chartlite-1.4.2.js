(function () {
  'use strict';
  window.ChartLite = {
    version: '1.4.2',
    render: function (target, values) {
      var label = document.createElement('p');
      label.className = 'chartlite-summary';
      label.textContent = 'Seven-day activity: ' + values.join(', ');
      target.replaceChildren(label);
    }
  };
}());
