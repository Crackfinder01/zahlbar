import type { IAuthenticateGeneric, ICredentialTestRequest, ICredentialType, INodeProperties } from 'n8n-workflow';

export class ZahlbarApi implements ICredentialType {
	name = 'zahlbarApi';

	displayName = 'Zahlbar API';

	documentationUrl = 'https://github.com/zahlbar/zahlbar#rest-api';

	properties: INodeProperties[] = [
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

	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				Authorization: '=Bearer {{$credentials.apiKey}}',
			},
		},
	};

	test: ICredentialTestRequest = {
		request: {
			baseURL: '={{$credentials.baseUrl}}',
			url: '/v1/invoices',
			qs: { status: 'overdue' },
		},
	};
}
