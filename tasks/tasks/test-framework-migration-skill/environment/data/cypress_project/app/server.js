const http = require('http');
const fs = require('fs');
const path = require('path');

const port = Number(process.env.PORT || 4173);
const catalogPath = path.join(__dirname, '..', 'cypress', 'fixtures', 'catalog.json');
const catalog = JSON.parse(fs.readFileSync(catalogPath, 'utf8'));
const featured = catalog.filter((product) => ['P-001', 'P-042', 'P-200'].includes(product.sku));

function money(cents) {
  return `$${(cents / 100).toFixed(2)}`;
}

function checkoutPage() {
  const options = featured.map((product) =>
    `<option value="${product.sku}" data-stock="${product.in_stock}">${product.name} — ${money(product.price_cents)}</option>`
  ).join('');
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Northstar Checkout</title></head>
<body>
  <main>
    <h1>Checkout</h1>
    <label>Product <select data-testid="product">${options}</select></label>
    <label>Quantity <input data-testid="quantity" type="number" min="1" value="1"></label>
    <label>Shipping <select data-testid="shipping"><option value="standard">Standard</option><option value="express">Express</option></select></label>
    <label>Promo code <input data-testid="promo"></label>
    <p data-testid="stock-warning" hidden>Selected product is out of stock.</p>
    <button data-testid="place-order">Place order</button>
    <section data-testid="quote-error" role="alert" hidden></section>
    <section data-testid="confirmation" hidden>
      <h2>Order confirmed</h2>
      <dl>
        <dt>Subtotal</dt><dd data-testid="subtotal"></dd>
        <dt>Discount</dt><dd data-testid="discount"></dd>
        <dt>Shipping</dt><dd data-testid="shipping-cost"></dd>
        <dt>Total</dt><dd data-testid="total"></dd>
      </dl>
      <a data-testid="receipt-link" target="_blank" rel="noopener"></a>
    </section>
  </main>
<script>
const product = document.querySelector('[data-testid="product"]');
const quantity = document.querySelector('[data-testid="quantity"]');
const shipping = document.querySelector('[data-testid="shipping"]');
const promo = document.querySelector('[data-testid="promo"]');
const submit = document.querySelector('[data-testid="place-order"]');
const warning = document.querySelector('[data-testid="stock-warning"]');
const error = document.querySelector('[data-testid="quote-error"]');
const confirmation = document.querySelector('[data-testid="confirmation"]');
const money = (cents) => '$' + (cents / 100).toFixed(2);
const show = (element, text) => { if (text !== undefined) element.textContent = text; element.hidden = false; };
const hide = (element) => { element.hidden = true; };
function updateStock() {
  const inStock = product.selectedOptions[0].dataset.stock === 'true';
  warning.hidden = inStock;
  submit.disabled = !inStock;
}
product.addEventListener('change', updateStock);
updateStock();
submit.addEventListener('click', async () => {
  if (!quantity.reportValidity()) return;
  hide(error); hide(confirmation);
  const body = { sku: product.value, quantity: Number(quantity.value), shipping: shipping.value, promo: promo.value };
  let response;
  try {
    response = await fetch('/api/quote', { method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(body) });
  } catch (_) {
    show(error, 'Unable to price order. Try again.'); return;
  }
  if (!response.ok) { show(error, 'Unable to price order. Try again.'); return; }
  const quote = await response.json();
  document.querySelector('[data-testid="subtotal"]').textContent = money(quote.subtotal_cents);
  document.querySelector('[data-testid="discount"]').textContent = money(quote.discount_cents);
  document.querySelector('[data-testid="shipping-cost"]').textContent = money(quote.shipping_cents);
  document.querySelector('[data-testid="total"]').textContent = money(quote.total_cents);
  const receipt = document.querySelector('[data-testid="receipt-link"]');
  receipt.href = '/receipt?order=' + encodeURIComponent(quote.order_id);
  receipt.textContent = 'Open receipt ' + quote.order_id;
  show(confirmation);
});
</script></body></html>`;
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => { try { resolve(JSON.parse(body)); } catch (error) { reject(error); } });
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (req.method === 'GET' && (url.pathname === '/' || url.pathname === '/checkout')) {
    res.writeHead(200, {'content-type': 'text/html; charset=utf-8'});
    return res.end(checkoutPage());
  }
  if (req.method === 'GET' && url.pathname === '/receipt') {
    res.writeHead(200, {'content-type': 'text/html; charset=utf-8'});
    return res.end(`<!doctype html><html><body><h1>Receipt</h1><p data-testid="receipt-order">${url.searchParams.get('order') || ''}</p></body></html>`);
  }
  if (req.method === 'POST' && url.pathname === '/api/quote') {
    try {
      const input = await readJson(req);
      const selected = catalog.find((product) => product.sku === input.sku);
      if (!selected || !selected.in_stock || !Number.isInteger(input.quantity) || input.quantity < 1) {
        res.writeHead(409, {'content-type': 'application/json'});
        return res.end(JSON.stringify({error: 'order cannot be quoted'}));
      }
      await new Promise((resolve) => setTimeout(resolve, 180));
      const subtotal = selected.price_cents * input.quantity;
      const discount = String(input.promo || '').toUpperCase() === 'SAVE10' ? Math.round(subtotal * 0.10) : 0;
      const shippingCents = input.shipping === 'express' ? 1500 : (subtotal >= 10000 ? 0 : 500);
      const quote = {
        order_id: `ORD-${selected.sku.slice(2)}-${input.quantity}`,
        subtotal_cents: subtotal,
        discount_cents: discount,
        shipping_cents: shippingCents,
        total_cents: subtotal - discount + shippingCents,
      };
      res.writeHead(200, {'content-type': 'application/json'});
      return res.end(JSON.stringify(quote));
    } catch (_) {
      res.writeHead(400, {'content-type': 'application/json'});
      return res.end(JSON.stringify({error: 'invalid json'}));
    }
  }
  res.writeHead(404, {'content-type': 'text/plain'});
  res.end('not found');
});

server.listen(port, '127.0.0.1', () => console.log(`checkout app listening on ${port}`));
