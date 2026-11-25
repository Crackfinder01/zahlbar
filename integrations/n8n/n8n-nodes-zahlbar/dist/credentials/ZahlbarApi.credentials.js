"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ZahlbarApi = void 0;
class ZahlbarApi {
    constructor() {
        this.name = 'zahlbarApi';
        this.displayName = 'Zahlbar API';
        this.documentationUrl = 'https://github.com/zahlbar/zahlbar#rest-api';
        this.properties = [
            {
                displayName: 'Base URL',
                name: 'baseUrl',
                type: 'string',
                default: 'http://localhost:8080',
                placeholder: 'https://zahlbar.example.com',
                description: 'URL of your self-hosted Zahlbar server (or the hosted version)',
            },
            {
                displayName: 'API Key',
                name: 'apiKey',
                type: 'string',
                typeOptions: { password: true },
                default: '',
                description: 'Value of ZAHLBAR_API_KEY on the server',
            },
        ];
        this.authenticate = {
            type: 'generic',
            properties: {
                headers: {
                    Authorization: '=Bearer {{$credentials.apiKey}}',
                },
            },
        };
        this.test = {
            request: {
                baseURL: '={{$credentials.baseUrl}}',
                url: '/v1/invoices',
                qs: { status: 'overdue' },
            },
        };
    }
}
exports.ZahlbarApi = ZahlbarApi;
