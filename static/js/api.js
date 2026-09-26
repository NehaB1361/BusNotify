/**
 * BusNotify - API Client Layer
 * Unified fetch wrapper with error handling, JSON parsing, and standard responses.
 */

const API = {
  async request(endpoint, options = {}) {
    const config = {
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
      config.body = JSON.stringify(config.body);
    }

    try {
      const response = await fetch(endpoint, config);
      const data = await response.json();

      if (!response.ok || !data.success) {
        const errorMsg = data?.error?.message || 'An unexpected error occurred';
        console.error(`[API ERROR ${response.status}]`, data);
        throw new Error(errorMsg);
      }

      return data.data;
    } catch (err) {
      console.error('[API Fetch Failed]', err);
      throw err;
    }
  },

  get(endpoint) {
    return this.request(endpoint, { method: 'GET' });
  },

  post(endpoint, body) {
    return this.request(endpoint, { method: 'POST', body });
  },

  put(endpoint, body) {
    return this.request(endpoint, { method: 'PUT', body });
  },

  delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  },

  async upload(endpoint, formData) {
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data?.error?.message || 'Upload failed');
      }
      return data.data;
    } catch (err) {
      console.error('[Upload Error]', err);
      throw err;
    }
  }
};
