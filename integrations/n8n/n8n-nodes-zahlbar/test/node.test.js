const test = require('node:test');
const assert = require('node:assert');
const { Zahlbar } = require('../dist/nodes/Zahlbar/Zahlbar.node.js');
const { ZahlbarApi } = require('../dist/credentials/ZahlbarApi.credentials.js');
const pkg = require('../package.json');

test('package declares the compiled node and credentials', () => {
  assert.ok(pkg.keywords.includes('n8n-community-node-package'));
  for (const file of [...pkg.n8n.nodes, ...pkg.n8n.credentials]) require(`../${file}`);
});

test('every operation routes to a Zahlbar endpoint', () => {
  const d = new Zahlbar().description;
  const ops = d.properties.find((p) => p.name === 'operation').options;
  const urls = Object.fromEntries(ops.map((o) => [o.value, o.routing.request.url]));
  assert.deepStrictEqual(urls, {
    createInvoice: '/v1/invoices',
    listInvoices: '/v1/invoices',
    getBill: '=/v1/invoices/{{$parameter.invoiceId}}/bill.pdf',
    reconcile: '/v1/reconcile',
    unmatched: '/v1/payments/unmatched',
  });
  assert.strictEqual(d.credentials[0].name, new ZahlbarApi().name);
});

test('credentials send a bearer token and hide the key', () => {
  const c = new ZahlbarApi();
  assert.strictEqual(c.authenticate.properties.headers.Authorization, '=Bearer {{$credentials.apiKey}}');
  assert.strictEqual(c.properties.find((p) => p.name === 'apiKey').typeOptions.password, true);
});

test('every parameter shown for an operation exists', () => {
  const d = new Zahlbar().description;
  const ops = new Set(d.properties.find((p) => p.name === 'operation').options.map((o) => o.value));
  for (const p of d.properties.filter((p) => p.displayOptions)) {
    for (const op of p.displayOptions.show.operation) assert.ok(ops.has(op), `${p.name} -> ${op}`);
  }
});
