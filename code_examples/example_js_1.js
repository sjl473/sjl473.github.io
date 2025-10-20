class APIError extends Error {
	constructor(message, status, code) {
		super(message);
		this.name = 'APIError';
		this.status = status;
		this.code = code;
	}
}

async function robustAPICall(endpoint, options = {}) {
	const controller = new AbortController();
	const timeoutId = setTimeout(() => controller.abort(), 10000);
	
	try {
		const response = await fetch(endpoint, {
			...options,
			signal: controller.signal
		});
		
		clearTimeout(timeoutId);
		
		if (!response.ok) {
			throw new APIError(
				`Request failed: ${response.statusText}`,
				response.status,
				'HTTP_ERROR'
			);
		}
		
		return await response.json();
	} catch (error) {
		clearTimeout(timeoutId);
		
		if (error.name === 'AbortError') {
			throw new APIError('Request timeout', 408, 'TIMEOUT');
		}
		
		throw error;
	}
}