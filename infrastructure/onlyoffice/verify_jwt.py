import json
with open('/etc/onlyoffice/documentserver/local.json') as f:
    cfg = json.load(f)
token = cfg['services']['CoAuthoring']['token'].get('browser', {})
secret = cfg['services']['CoAuthoring']['secret'].get('browser', {})
print('token browser:', token)
print('secret browser:', secret)
