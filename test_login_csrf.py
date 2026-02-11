#!/usr/bin/env python
"""
Test CSRF token flow on login page:
1. GET /login/ — extract CSRF token from cookie and form
2. POST /login/ with username, password, and CSRF token
Verify that the POST succeeds (200 or redirect) without 403 Forbidden.
"""
import requests
from http.cookiejar import CookieJar
import re

BASE_URL = 'http://127.0.0.1:8000'

# Create a session to persist cookies (like a browser)
session = requests.Session()
session.cookies = CookieJar()

print('=== Step 1: GET /login/ ===')
resp_get = session.get(f'{BASE_URL}/login/')
print(f'Status: {resp_get.status_code}')
print(f'Cookies after GET: {list(session.cookies)}')

# Extract CSRF token from form (looks for name="csrfmiddlewaretoken" value="...")
match = re.search(r'name=["\']csrfmiddlewaretoken["\'].*?value=["\']([^"\']+)["\']', resp_get.text)
csrf_token = match.group(1) if match else None
print(f'CSRF token from form: {csrf_token[:20]}...' if csrf_token else 'CSRF token: NOT FOUND')

if not csrf_token:
    print('ERROR: No CSRF token found in form. Check if @ensure_csrf_cookie is working.')
    exit(1)

print('\n=== Step 2: POST /login/ ===')
# Try login with a non-existent user (we just want to test CSRF, not actual auth)
login_data = {
    'username': 'testuser_does_not_exist',
    'password': 'testpass',
    'csrfmiddlewaretoken': csrf_token,
}
resp_post = session.post(f'{BASE_URL}/login/?next=/dashboard/', data=login_data, allow_redirects=False)
print(f'Status: {resp_post.status_code}')

if resp_post.status_code == 403:
    print('ERROR: Got 403 Forbidden — CSRF token was rejected!')
    print('Response body:', resp_post.text[:200])
    exit(1)
elif resp_post.status_code == 200:
    print('OK: Got 200 — form accepted and re-rendered (auth failed as expected since user is fake)')
    if 'Invalid username or password' in resp_post.text or 'error' in resp_post.text.lower():
        print('Confirmation: Error message for invalid credentials found in response')
    exit(0)
elif resp_post.status_code in (301, 302, 303, 307):
    print(f'OK: Got {resp_post.status_code} redirect — form was accepted and redirected')
    exit(0)
else:
    print(f'Unexpected status: {resp_post.status_code}')
    exit(1)
