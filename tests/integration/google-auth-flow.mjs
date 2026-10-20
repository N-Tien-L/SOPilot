// Real HTTP + two Spring Boot processes + fresh PostgreSQL. Google JWKS is local.
// No project .env files, existing containers/volumes, or real Google accounts are used.
import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { generateKeyPairSync, randomBytes, randomUUID, sign } from 'node:crypto';
import { createServer } from 'node:http';
import { createServer as tcpServer } from 'node:net';
import { mkdirSync, readFileSync, writeFileSync, openSync, closeSync, existsSync, readdirSync } from 'node:fs';
import { resolve, dirname, delimiter } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const runId = randomUUID();
const scratch = resolve(root, 'scratch', `google-auth-${runId}`);
mkdirSync(scratch, { recursive: true });
console.log(`Isolated backend logs: ${scratch}`);
const container = `sopilot-google-auth-test-${runId}`;
const children = [];
const handles = [];
const results = [];
let containerCreated = false;
const clientId = 'sopilot-isolated-test-client';
const issuer = 'https://accounts.google.com';
const secret = randomBytes(48).toString('hex');
const serviceToken = randomBytes(32).toString('hex');
const adminPassword = randomBytes(24).toString('hex');
const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
const jwk = { ...publicKey.export({ format: 'jwk' }), kid: 'local-test-key', alg: 'RS256', use: 'sig' };
const jwks = createServer((_req, res) => {
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ keys: [jwk] }));
});

function docker(args, input) {
  return execFileSync('docker', args, { input, encoding: 'utf8', timeout: 30_000, stdio: ['pipe', 'pipe', 'pipe'] }).trim();
}
function sql(statement) {
  assert(container.startsWith('sopilot-google-auth-test-'));
  return docker(['exec', '-i', container, 'psql', '-U', 'sopilot_test', '-d', 'sopilot_google_auth_test', '-v', 'ON_ERROR_STOP=1', '-t', '-A'], statement);
}
async function unusedPort() {
  const server = tcpServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return port;
}
function idToken(email, sub, overrides = {}) {
  const header = Buffer.from(JSON.stringify({ alg: 'RS256', kid: jwk.kid })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({ iss: issuer, aud: clientId, sub,
    exp: Math.floor(Date.now() / 1000) + 600, iat: Math.floor(Date.now() / 1000),
    email, email_verified: true, hd: 'company.test', ...overrides })).toString('base64url');
  const data = `${header}.${payload}`;
  return `${data}.${sign('RSA-SHA256', Buffer.from(data), privateKey).toString('base64url')}`;
}
async function request(base, path, body, bearer) {
  const response = await fetch(`${base}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(30_000),
  });
  return { status: response.status, body: await response.json() };
}
function start(service, port, dbPort, otherPort, jwksPort) {
  const classpathFile = resolve(root, `services/${service}/target/runtime-classpath.txt`);
  const jar = readdirSync(resolve(root, `services/${service}/target`))
    .find(name => name.endsWith('.jar') && !name.endsWith('.original'));
  assert(jar || existsSync(classpathFile), `Compile ${service} and generate target/runtime-classpath.txt first`);
  const config = {
    'server.address': '127.0.0.1', 'server.port': port,
    'spring.application.name': service,
    'spring.datasource.url': `jdbc:postgresql://127.0.0.1:${dbPort}/sopilot_google_auth_test`,
    'spring.datasource.username': 'sopilot_test', 'spring.datasource.password': '',
    'spring.datasource.hikari.maximum-pool-size': 8, 'spring.datasource.hikari.minimum-idle': 1,
    'spring.jpa.hibernate.ddl-auto': 'validate', 'spring.jpa.open-in-view': false,
    'spring.jpa.properties.hibernate.default_schema': 'core',
    'spring.cloud.compatibility-verifier.enabled': false,
    'spring.rabbitmq.host': '127.0.0.1', 'spring.rabbitmq.port': 9,
    'spring.rabbitmq.listener.simple.auto-startup': false,
    'spring.rabbitmq.listener.direct.auto-startup': false,
    'management.health.rabbit.enabled': false,
    'auth.jwt.secret': secret, 'auth.jwt.issuer': 'sopilot-test',
    'auth.jwt.access-token-ttl': 'PT15M', 'auth.refresh-token.ttl': 'P7D',
    'auth.login.max-failed-attempts': 5, 'auth.login.lock-duration': 'PT15M',
    'auth.oauth.google.client-id': clientId,
    'auth.oauth.google.jwks-uri': `http://127.0.0.1:${jwksPort}/jwks`,
    'app.services.user-service-url': `http://127.0.0.1:${otherPort}`,
    'app.services.feedback-service-url': 'http://127.0.0.1:9',
    'poliwise.jwt.secret': secret, 'poliwise.jwt.issuer': 'sopilot-test',
    'poliwise.service-token': serviceToken, 'poliwise.bootstrap.admin.enabled': service === 'auth-service',
    'ADMIN_USERNAME': 'auth_test_admin', 'ADMIN_EMAIL': 'admin@company.test', 'ADMIN_PASSWORD': adminPassword,
    'email.enabled': false, 'email.from-name': 'Auth Test', 'email.from-address': 'test@company.test',
    'spring.mail.host': '127.0.0.1', 'spring.mail.port': 9,
    'logging.level.root': 'WARN',
  };
  const props = resolve(scratch, `${service}.properties`);
  writeFileSync(props, Object.entries(config).map(([key, value]) => `${key}=${value}`).join('\n'));
  const log = openSync(resolve(scratch, `${service}.log`), 'a');
  handles.push(log);
  const launch = existsSync(classpathFile)
    ? ['-cp', resolve(root, `services/${service}/target/classes`) + delimiter + readFileSync(classpathFile, 'utf8').trim(),
      service === 'auth-service' ? 'com.poliwise.auth.AuthServiceApplication' : 'com.poliwise.user.UserServiceApplication']
    : ['-jar', resolve(root, `services/${service}/target/${jar}`)];
  const child = spawn('java', [...launch,
    `--spring.config.location=file:${props.replaceAll('\\', '/')}`,
    // Explicit CLI values override any developer machine SPRING_* environment settings.
    ...Object.entries(config).map(([key, value]) => `--${key}=${value}`)], {
    cwd: scratch, windowsHide: true, stdio: ['ignore', log, log],
  });
  children.push(child);
  child.on('error', error => { console.error(`Cannot start ${service}: ${error.message}`); });
  return child;
}
async function ready(base, child) {
  for (let attempt = 0; attempt < 120; attempt++) {
    if (child.exitCode !== null) throw new Error(`Service exited; inspect logs in ${scratch}`);
    try {
      const response = await fetch(`${base}/actuator/health`, { signal: AbortSignal.timeout(1000) });
      if (response.ok) return;
    } catch { /* retry only while startup is in progress */ }
    await delay(1000);
  }
  throw new Error(`Startup timed out; inspect logs in ${scratch}`);
}
async function check(name, fn) {
  await fn();
  results.push(name);
  console.log(`PASS ${name}`);
}
function roster(email, code, role = 'USER') {
  sql(`INSERT INTO core.employee_roster (id,employee_code,email,full_name,department_id,role,status,is_claimed)
    VALUES ('${randomUUID()}','${code}','${email}','Test Employee','${departmentId}','${role}','PENDING',false);`);
}
const departmentId = randomUUID();

try {
  docker(['run', '--pull=never', '--rm', '-d', '--name', container,
    '--label', `sopilot.google-auth-test=${runId}`, '-e', 'POSTGRES_HOST_AUTH_METHOD=trust',
    '-e', 'POSTGRES_USER=sopilot_test', '-e', 'POSTGRES_DB=sopilot_google_auth_test',
    '-p', '127.0.0.1::5432', 'pgvector/pgvector:pg16']);
  containerCreated = true;
  for (let attempt = 0; ; attempt++) {
    try { sql('SELECT 1;'); break; } catch (error) { if (attempt > 45) throw error; await delay(1000); }
  }
  // Only core/auth migrations are needed; this suite does not certify the document/RAG schemas.
  for (const file of ['000_bootstrap.sql', '001_core.sql', '010_employee_roster.sql', '012_google_identities.sql']) {
    sql(readFileSync(resolve(root, 'infrastructure/init-db', file), 'utf8'));
  }
  // The migration itself must be safe to apply twice.
  sql(readFileSync(resolve(root, 'infrastructure/init-db/012_google_identities.sql'), 'utf8'));
  sql(`INSERT INTO core.departments(id,name,code) VALUES('${departmentId}','Engineering','ENG');`);
  const dbPort = JSON.parse(docker(['inspect', '--format', '{{json .NetworkSettings.Ports}}', container]))['5432/tcp'][0].HostPort;
  await new Promise(resolve => jwks.listen(0, '127.0.0.1', resolve));
  const jwksPort = jwks.address().port;
  const userPort = await unusedPort();
  const authPort = await unusedPort();
  const userBase = `http://127.0.0.1:${userPort}`;
  const authBase = `http://127.0.0.1:${authPort}`;
  await ready(userBase, start('user-service', userPort, dbPort, authPort, jwksPort));
  await ready(authBase, start('auth-service', authPort, dbPort, userPort, jwksPort));
  const login = (email, sub, overrides) => request(authBase, '/api/v1/auth/google/verify', { idToken: idToken(email, sub, overrides) });
  let session;
  await check('new roster enrollment creates one subject link and the expected role/department', async () => {
    roster('employee@company.test', 'EMP001');
    session = await login('employee@company.test', 'subject-1');
    assert.equal(session.status, 200);
    assert.equal(session.body.user.role, 'USER');
    assert.equal(sql("SELECT count(*) FROM core.external_identities WHERE subject='subject-1';"), '1');
    assert.equal(sql("SELECT status FROM core.employee_roster WHERE employee_code='EMP001';"), 'CLAIMED');
    assert.equal(sql(`SELECT department_id FROM core.users WHERE id='${session.body.user.id}';`), departmentId);
  });
  await check('returning login stays on the same account', async () => {
    const again = await login('employee@company.test', 'subject-1');
    assert.equal(again.status, 200);
    assert.equal(again.body.user.id, session.body.user.id);
  });
  await check('stable subject survives an email change without transferring to another account', async () => {
    const result = await login('renamed@company.test', 'subject-1');
    assert.equal(result.status, 200);
    assert.equal(result.body.user.id, session.body.user.id);
  });
  await check('a different subject cannot take the same email', async () => {
    assert.equal((await login('employee@company.test', 'attacker-subject')).status, 409);
  });
  await check('Google issuer aliases resolve to the canonical stored identity', async () => {
    assert.equal((await login('employee@company.test', 'subject-1', { iss: 'accounts.google.com' })).status, 200);
    assert.equal(sql("SELECT issuer FROM core.external_identities WHERE subject='subject-1';"), issuer);
  });
  await check('an alias roster email cannot bypass the one-Google-identity-per-user constraint', async () => {
    sql("UPDATE core.employee_roster SET email='alias@company.test' WHERE employee_code='EMP001';");
    assert.equal((await login('alias@company.test', 'alias-attacker')).status, 409);
    assert.equal(sql("SELECT count(*) FROM core.external_identities WHERE subject='alias-attacker';"), '0');
    sql("UPDATE core.employee_roster SET email='employee@company.test' WHERE employee_code='EMP001';");
  });
  await check('outsider is rejected before a local account/session is created', async () => {
    assert.equal((await login('outsider@company.test', 'outsider')).status, 403);
    assert.equal(sql("SELECT count(*) FROM core.users WHERE email='outsider@company.test';"), '0');
  });
  await check('claimed roster deactivation blocks the next Google login', async () => {
    sql("UPDATE core.employee_roster SET status='DEACTIVATED' WHERE employee_code='EMP001';");
    assert.equal((await login('employee@company.test', 'subject-1')).status, 403);
    sql("UPDATE core.employee_roster SET status='CLAIMED' WHERE employee_code='EMP001';");
  });
  await check('removed roster blocks a returning linked account', async () => {
    sql("UPDATE core.employee_roster SET deleted_at=now() WHERE employee_code='EMP001';");
    assert.equal((await login('employee@company.test', 'subject-1')).status, 403);
    sql("UPDATE core.employee_roster SET deleted_at=NULL WHERE employee_code='EMP001';");
  });
  for (const status of ['DEACTIVATED', 'REVOKED']) {
    await check(`${status} local account cannot log in with Google`, async () => {
      sql(`UPDATE core.users SET status='${status}',deactivated_at=now(),revoked_at=now() WHERE id='${session.body.user.id}';`);
      assert.equal((await login('employee@company.test', 'subject-1')).status, 403);
      assert.equal((await request(authBase, '/api/v1/auth/refresh', { refreshToken: session.body.refreshToken })).status, 401);
      sql(`UPDATE core.users SET status='ACTIVE' WHERE id='${session.body.user.id}';`);
    });
  }
  await check('temporarily locked account cannot log in with Google', async () => {
    sql(`UPDATE core.users SET locked_until=now()+interval '5 minutes' WHERE id='${session.body.user.id}';`);
    assert.equal((await login('employee@company.test', 'subject-1')).status, 403);
    sql(`UPDATE core.users SET locked_until=NULL WHERE id='${session.body.user.id}';`);
  });
  for (const [name, overrides] of [['wrong audience', { aud: 'other-app' }], ['wrong issuer', { iss: 'https://attacker.test' }],
    ['expired token', { exp: 1 }], ['missing subject', { sub: '' }], ['unverified email', { email_verified: false }]]) {
    await check(`reject ${name}`, async () => assert.equal((await login('employee@company.test', 'subject-1', overrides)).status, 401));
  }
  await check('unbound third-party email needs additional ownership proof', async () => {
    assert.equal((await login('unbound@company.test', 'unbound-subject', { hd: undefined })).status, 403);
  });
  await check('bound subject remains valid when email authority changes', async () => {
    const result = await login('renamed@third-party.test', 'subject-1', { hd: undefined });
    assert.equal(result.status, 200);
    assert.equal(result.body.user.id, session.body.user.id);
  });
  await check('invalid signature is rejected', async () => {
    const token = idToken('employee@company.test', 'subject-1');
    const parts = token.split('.');
    parts[2] = Buffer.from(randomBytes(256)).toString('base64url');
    assert.equal((await request(authBase, '/api/v1/auth/google/verify', { idToken: parts.join('.') })).status, 401);
  });
  await check('parallel first login is idempotent at the database boundary', async () => {
    for (let batch = 0; batch < 3; batch++) {
      const email = `parallel${batch}@company.test`;
      const subject = `parallel-subject-${batch}`;
      roster(email, `PAR${batch}`);
      const responses = await Promise.all(Array.from({ length: 6 }, () => login(email, subject)));
      assert(responses.every(response => response.status === 200), `Statuses: ${responses.map(response => response.status)}`);
      assert.equal(new Set(responses.map(response => response.body.user.id)).size, 1);
      assert.equal(sql(`SELECT count(*) FROM core.external_identities WHERE subject='${subject}';`), '1');
      assert.equal(sql(`SELECT count(*) FROM core.users WHERE email='${email}';`), '1');
    }
  });
  await check('admin password login works without a roster, Google admission has no admin bypass', async () => {
    const admin = await request(authBase, '/api/v1/auth/login', { username: 'auth_test_admin', password: adminPassword });
    assert.equal(admin.status, 200);
    assert.equal(admin.body.user.role, 'ADMIN');
    assert.equal((await login('admin@company.test', 'admin-subject')).status, 403);
  });
  await check('legacy account must enroll through a matching roster before Google login', async () => {
    sql(`INSERT INTO core.users(id,username,email,password_hash,role,status,department_id)
      VALUES('${randomUUID()}','legacy_test','legacy@company.test','unusable','USER','ACTIVE','${departmentId}');`);
    assert.equal((await login('legacy@company.test', 'legacy-subject')).status, 403);
    roster('legacy@company.test', 'EMP003');
    const result = await login('legacy@company.test', 'legacy-subject');
    assert.equal(result.status, 200);
    assert.equal(sql("SELECT count(*) FROM core.users WHERE email='legacy@company.test';"), '1');
  });
  await check('legacy privileges cannot be silently changed by enrollment', async () => {
    sql(`INSERT INTO core.users(id,username,email,password_hash,role,status,department_id)
      VALUES('${randomUUID()}','legacy_admin','legacyadmin@company.test','unusable','ADMIN','ACTIVE','${departmentId}');`);
    roster('legacyadmin@company.test', 'EMP004', 'USER');
    assert.equal((await login('legacyadmin@company.test', 'legacy-admin-subject')).status, 409);
    assert.equal(sql("SELECT role FROM core.users WHERE email='legacyadmin@company.test';"), 'ADMIN');
    assert.equal(sql("SELECT status FROM core.employee_roster WHERE employee_code='EMP004';"), 'PENDING');
  });
  await check('refresh replay durably revokes all remaining refresh sessions', async () => {
    const rotated = await request(authBase, '/api/v1/auth/refresh', { refreshToken: session.body.refreshToken });
    assert.equal(rotated.status, 200);
    assert.equal((await request(authBase, '/api/v1/auth/refresh', { refreshToken: session.body.refreshToken })).status, 401);
    assert.equal(sql(`SELECT count(*) FROM core.refresh_tokens WHERE user_id='${session.body.user.id}' AND revoked=false;`), '0');
    assert.equal((await request(authBase, '/api/v1/auth/refresh', { refreshToken: rotated.body.refreshToken })).status, 401);
  });
  await check('logout revokes the refresh session and blacklists its access token', async () => {
    const fresh = await login('employee@company.test', 'subject-1');
    assert.equal(fresh.status, 200);
    const rotated = await request(authBase, '/api/v1/auth/refresh', { refreshToken: fresh.body.refreshToken });
    assert.equal(rotated.status, 200);
    const logout = await request(authBase, '/api/v1/auth/logout', { refreshToken: rotated.body.refreshToken }, rotated.body.accessToken);
    assert.equal(logout.status, 200);
    assert.equal((await request(authBase, '/api/v1/auth/refresh', { refreshToken: rotated.body.refreshToken })).status, 401);
    assert.equal((await request(authBase, '/api/v1/auth/me', undefined, rotated.body.accessToken)).status, 401);
  });
  await check('expired refresh token rejection persists the expiration revocation', async () => {
    const fresh = await login('employee@company.test', 'subject-1');
    assert.equal(fresh.status, 200);
    sql(`UPDATE core.refresh_tokens SET expires_at=now()-interval '1 minute' WHERE user_id='${session.body.user.id}' AND revoked=false;`);
    assert.equal((await request(authBase, '/api/v1/auth/refresh', { refreshToken: fresh.body.refreshToken })).status, 401);
    assert.equal(sql(`SELECT count(*) FROM core.refresh_tokens WHERE user_id='${session.body.user.id}' AND revoked_reason='EXPIRED';`), '1');
  });
  await check('internal admission endpoint rejects a missing service credential', async () => {
    const result = await request(userBase, '/internal/v1/roster/google-admission', { email: 'employee@company.test' });
    assert.equal(result.status, 401);
  });
  writeFileSync(resolve(scratch, 'results.json'), JSON.stringify({ passed: results.length, tests: results }, null, 2));
  console.log(`Passed ${results.length} isolated backend checks. Logs: ${scratch}`);
} finally {
  for (const child of children) {
    if (child.exitCode === null) {
      child.kill();
      await Promise.race([new Promise(resolve => child.once('exit', resolve)), delay(5000)]);
    }
  }
  jwks.close();
  for (const handle of handles) closeSync(handle);
  if (containerCreated) {
    const label = docker(['inspect', '--format', '{{index .Config.Labels "sopilot.google-auth-test"}}', container]);
    assert.equal(label, runId, 'Refuse to remove a container not owned by this test');
    docker(['rm', '-f', container]);
  }
}
