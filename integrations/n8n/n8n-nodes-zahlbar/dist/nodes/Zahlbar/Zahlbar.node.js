"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.Zahlbar = void 0;
/**
 * Declarative n8n node: every operation maps to one call of the Zahlbar REST API.
 */
class Zahlbar {
    constructor() {
        this.description = {
            displayName: 'Zahlbar',
            name: 'zahlbar',
            icon: 'file:zahlbar.svg',
            group: ['transform'],
            version: 1,
            subtitle: '={{$parameter["operation"]}}',
            description: 'Swiss QR-bills that tell you who paid',
            defaults: { name: 'Zahlbar' },
            inputs: ['main'],
            outputs: ['main'],
            credentials: [{ name: 'zahlbarApi', required: true }],
            requestDefaults: {
                baseURL: '={{$credentials.baseUrl}}',
                headers: { Accept: 'application/json' },
            },
            properties: [
                {
                    displayName: 'Operation',
                    name: 'operation',
                    type: 'options',
                    noDataExpression: true,
                    default: 'createInvoice',
                    options: [
                        {
                            name: 'Create Invoice',
                            value: 'createInvoice',
                            action: 'Create an invoice with a QR reference',
                            routing: {
                                request: {
                                    method: 'POST',
                                    url: '/v1/invoices',
                                    body: {
                                        number: '={{$parameter.number}}',
                                        amount: '={{$parameter.amount}}',
                                        currency: '={{$parameter.currency}}',
                                        due_date: '={{$parameter.dueDate || undefined}}',
                                        message: '={{$parameter.message}}',
                                        language: '={{$parameter.language}}',
                                    },
                                },
                            },
                        },
                        {
                            name: 'List Invoices',
                            value: 'listInvoices',
                            action: 'List invoices by status',
                            routing: {
                                request: { method: 'GET', url: '/v1/invoices', qs: { status: '={{$parameter.status}}' } },
                                output: { postReceive: [{ type: 'rootProperty', properties: { property: '' } }] },
                            },
                        },
                        {
                            name: 'Get QR-Bill (PDF)',
                            value: 'getBill',
                            action: 'Get the QR bill PDF of an invoice',
                            routing: {
                                request: {
                                    method: 'GET',
                                    url: '=/v1/invoices/{{$parameter.invoiceId}}/bill.pdf',
                                    encoding: 'arraybuffer',
                                    returnFullResponse: false,
                                },
                                output: { postReceive: [{ type: 'binaryData', properties: { destinationProperty: 'data' } }] },
                            },
                        },
                        {
                            name: 'Reconcile Bank File',
                            value: 'reconcile',
                            action: 'Import a camt 054 or camt 053 file and mark paid invoices',
                            routing: {
                                request: {
                                    method: 'POST',
                                    url: '/v1/reconcile',
                                    headers: { 'Content-Type': 'application/xml' },
                                    body: '={{$parameter.camtXml}}',
                                    json: false,
                                },
                            },
                        },
                        {
                            name: 'List Unmatched Payments',
                            value: 'unmatched',
                            action: 'List payments that match no invoice',
                            routing: { request: { method: 'GET', url: '/v1/payments/unmatched' } },
                        },
                    ],
                },
                // ---- Create invoice -------------------------------------------------
                {
                    displayName: 'Invoice Number',
                    name: 'number',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: { show: { operation: ['createInvoice'] } },
                },
                {
                    displayName: 'Amount',
                    name: 'amount',
                    type: 'string',
                    required: true,
                    default: '',
                    placeholder: '120.50',
                    displayOptions: { show: { operation: ['createInvoice'] } },
                },
                {
                    displayName: 'Currency',
                    name: 'currency',
                    type: 'options',
                    options: [
                        { name: 'CHF', value: 'CHF' },
                        { name: 'EUR', value: 'EUR' },
                    ],
                    default: 'CHF',
                    displayOptions: { show: { operation: ['createInvoice'] } },
                },
                {
                    displayName: 'Due Date',
                    name: 'dueDate',
                    type: 'string',
                    default: '',
                    placeholder: '2026-12-31',
                    displayOptions: { show: { operation: ['createInvoice'] } },
                },
                {
                    displayName: 'Message',
                    name: 'message',
                    type: 'string',
                    default: '',
                    displayOptions: { show: { operation: ['createInvoice'] } },
                },
                {
                    displayName: 'Language',
                    name: 'language',
                    type: 'options',
                    options: [
                        { name: 'German', value: 'de' },
                        { name: 'English', value: 'en' },
                        { name: 'French', value: 'fr' },
                        { name: 'Italian', value: 'it' },
                    ],
                    default: 'de',
                    displayOptions: { show: { operation: ['createInvoice'] } },
                },
                // ---- List ----------------------------------------------------------
                {
                    displayName: 'Status',
                    name: 'status',
                    type: 'options',
                    options: [
                        { name: 'All', value: 'all' },
                        { name: 'Open', value: 'open' },
                        { name: 'Overdue', value: 'overdue' },
                        { name: 'Paid', value: 'paid' },
                        { name: 'Partially Paid', value: 'partial' },
                        { name: 'Unpaid (Open or Partial)', value: 'unpaid' },
                    ],
                    default: 'overdue',
                    displayOptions: { show: { operation: ['listInvoices'] } },
                },
                // ---- Bill ----------------------------------------------------------
                {
                    displayName: 'Invoice ID',
                    name: 'invoiceId',
                    type: 'string',
                    required: true,
                    default: '',
                    displayOptions: { show: { operation: ['getBill'] } },
                },
                // ---- Reconcile -----------------------------------------------------
                {
                    displayName: 'camt XML',
                    name: 'camtXml',
                    type: 'string',
                    typeOptions: { rows: 6 },
                    required: true,
                    default: '',
                    description: 'Content of the camt.054 or camt.053 file (for example from an e-mail attachment)',
                    displayOptions: { show: { operation: ['reconcile'] } },
                },
            ],
        };
    }
}
exports.Zahlbar = Zahlbar;
