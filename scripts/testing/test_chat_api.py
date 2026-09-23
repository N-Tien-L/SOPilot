import httpx
import time

time.sleep(10)  # Wait for rate limit to reset

credentials_list = [
    {'email': 'admin', 'password': 'Admin@123456'},
    {'email': 'admin@poliwise.com', 'password': 'Admin@123456'},
    {'email': 'admin@poliwise.local', 'password': 'Admin@123456'},
]

token = None
for cred in credentials_list:
    resp = httpx.post('http://localhost:3001/api/v1/auth/login', json=cred, timeout=10)
    if resp.status_code == 200:
        token = resp.json().get('accessToken', '')
        print(f'Login SUCCESS with {cred["email"]}')
        break
    else:
        print(f'Login failed for {cred["email"]}: {resp.status_code} - {resp.text[:100]}')

if not token:
    print('No valid credentials found')
    exit(1)

print(f'Token: {token[:30]}...')

# Test chat
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
data = {'message': 'Chính sách bảo mật thông tin quy định những gì?'}
print('Sending chat request...')
resp = httpx.post('http://localhost:3001/api/v1/ai/chat', json=data, headers=headers, timeout=120)
print(f'Chat response: {resp.status_code}')
print(f'Body: {resp.text[:5000]}')
