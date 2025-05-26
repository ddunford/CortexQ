import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 10 }, // Ramp up to 10 users
    { duration: '5m', target: 10 }, // Stay at 10 users
    { duration: '2m', target: 20 }, // Ramp up to 20 users
    { duration: '5m', target: 20 }, // Stay at 20 users
    { duration: '2m', target: 0 },  // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% of requests must complete below 2s
    http_req_failed: ['rate<0.1'],     // Error rate must be below 10%
    errors: ['rate<0.1'],              // Custom error rate must be below 10%
  },
};

// Base URL - can be overridden with environment variable
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8001';

// Test data
const testUser = {
  email: 'loadtest@example.com',
  password: 'loadtest123',
  full_name: 'Load Test User'
};

let authToken = '';

export function setup() {
  // Register test user
  const registerResponse = http.post(`${BASE_URL}/auth/register`, JSON.stringify(testUser), {
    headers: { 'Content-Type': 'application/json' },
  });
  
  if (registerResponse.status === 200) {
    const loginData = JSON.parse(registerResponse.body);
    return { token: loginData.access_token };
  }
  
  // If registration fails (user exists), try login
  const loginResponse = http.post(`${BASE_URL}/auth/login`, JSON.stringify({
    email: testUser.email,
    password: testUser.password
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
  
  if (loginResponse.status === 200) {
    const loginData = JSON.parse(loginResponse.body);
    return { token: loginData.access_token };
  }
  
  throw new Error('Failed to authenticate test user');
}

export default function(data) {
  const headers = {
    'Authorization': `Bearer ${data.token}`,
    'Content-Type': 'application/json',
  };

  // Test 1: Health check
  const healthResponse = http.get(`${BASE_URL}/health`);
  check(healthResponse, {
    'health check status is 200': (r) => r.status === 200,
    'health check response time < 500ms': (r) => r.timings.duration < 500,
  }) || errorRate.add(1);

  sleep(1);

  // Test 2: Get current user
  const userResponse = http.get(`${BASE_URL}/users/me`, { headers });
  check(userResponse, {
    'get user status is 200': (r) => r.status === 200,
    'get user response time < 1000ms': (r) => r.timings.duration < 1000,
    'user response has email': (r) => JSON.parse(r.body).email !== undefined,
  }) || errorRate.add(1);

  sleep(1);

  // Test 3: List files (should work even with empty list)
  const filesResponse = http.get(`${BASE_URL}/files?domain=general`, { headers });
  check(filesResponse, {
    'list files status is 200': (r) => r.status === 200,
    'list files response time < 1500ms': (r) => r.timings.duration < 1500,
    'files response is array': (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.files);
      } catch {
        return false;
      }
    },
  }) || errorRate.add(1);

  sleep(1);

  // Test 4: Search functionality
  const searchResponse = http.post(`${BASE_URL}/search`, JSON.stringify({
    query: 'test search query',
    domain: 'general',
    limit: 10
  }), { headers });
  
  check(searchResponse, {
    'search status is 200 or 404': (r) => r.status === 200 || r.status === 404,
    'search response time < 3000ms': (r) => r.timings.duration < 3000,
  }) || errorRate.add(1);

  sleep(2);

  // Test 5: Chat functionality (if available)
  const chatResponse = http.post(`${BASE_URL}/chat`, JSON.stringify({
    message: 'Hello, this is a load test message',
    domain: 'general'
  }), { headers });
  
  check(chatResponse, {
    'chat status is 200 or 404': (r) => r.status === 200 || r.status === 404,
    'chat response time < 5000ms': (r) => r.timings.duration < 5000,
  }) || errorRate.add(1);

  sleep(2);
}

export function teardown(data) {
  // Cleanup: logout user
  if (data.token) {
    http.post(`${BASE_URL}/auth/logout`, null, {
      headers: { 'Authorization': `Bearer ${data.token}` },
    });
  }
} 