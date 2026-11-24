import { Api, API_URL } from './support/api';
import { sopMarkdown } from './support/fixtures';
import { PERSONA_KEYS, saveWorld, type Persona, type PersonaKey, type World } from './support/world';

interface Plan {
  name: string;
  role: 'ADMIN' | 'MEMBER';
  department: 'alpha' | 'beta' | null;
}

type Invited = Exclude<PersonaKey, 'owner'>;

const PLAN: Record<Invited, Plan> = {
  admin: { name: 'E2E Admin', role: 'ADMIN', department: null },
  wsPub: { name: 'E2E Workspace Publisher', role: 'MEMBER', department: null },
  alphaPub: { name: 'E2E Alpha Publisher', role: 'MEMBER', department: 'alpha' },
  alphaMember: { name: 'E2E Alpha Member', role: 'MEMBER', department: 'alpha' },
  betaMember: { name: 'E2E Beta Member', role: 'MEMBER', department: 'beta' },
  loner: { name: 'E2E Loner', role: 'MEMBER', department: null },
  spareA: { name: 'E2E Spare A', role: 'MEMBER', department: null },
  spareB: { name: 'E2E Spare B', role: 'MEMBER', department: null },
};

/**
 * Builds one throwaway TEAM workspace through the API: departments, people in every role, publishers and
 * two documents. Everything lives in that workspace, so the owner real data is never touched, and
 * global-teardown deletes it.
 */
export default async function globalSetup(): Promise<void> {
  const api = await Api.create();
  try {
    if (!(await api.healthy())) {
      throw new Error(`core-api is not reachable at ${API_URL}. Start the stack (docs/operations/local-development.md).`);
    }
    const run = Date.now().toString(36);
    const email = (key: string) => `e2e-${run}-${key.toLowerCase()}@sopilot.local`;

    const ownerName = 'E2E Owner';
    let owner = await api.login(email('owner'), ownerName);
    const created = await api.ok(
      'create workspace',
      api.call('POST', '/workspaces', { token: owner.token, json: { name: `E2E ${run}` } }),
    );
    owner = { ...owner, token: created.accessToken };
    const workspaceId: string = created.workspace.id;

    const mkDept = async (name: string): Promise<string> =>
      (await api.ok(`create department ${name}`, api.call('POST', '/departments', { token: owner.token, json: { name } }))).id;
    const departments = { alpha: await mkDept('Alpha'), beta: await mkDept('Beta') };

    const personas = {
      owner: { key: 'owner', email: email('owner'), name: ownerName, userId: owner.userId },
    } as Record<PersonaKey, Persona>;

    // Invite without a name (it comes from the account), then accept as that person.
    for (const key of PERSONA_KEYS.filter((k) => k !== 'owner') as Invited[]) {
      const plan = PLAN[key];
      const invite = await api.ok(
        `invite ${key}`,
        api.call('POST', '/invitations', {
          token: owner.token,
          json: {
            email: email(key),
            role: plan.role,
            ...(plan.department ? { departmentId: departments[plan.department] } : {}),
          },
        }),
      );
      const session = await api.login(email(key), plan.name);
      await api.ok(
        `accept ${key}`,
        api.call('POST', '/invitations/accept', { token: session.token, json: { invitationId: invite.id } }),
      );
      personas[key] = { key, email: email(key), name: plan.name, userId: session.userId };
    }

    // The creator is the workspace publisher by default; move the role to wsPub so the OWNER is a plain owner.
    await api.ok(
      'workspace publisher',
      api.call('PUT', '/publishers/workspace', { token: owner.token, json: { userId: personas.wsPub.userId } }),
    );
    await api.ok(
      'alpha publisher',
      api.call('PUT', `/departments/${departments.alpha}/publisher`, {
        token: owner.token,
        json: { userId: personas.alphaPub.userId },
      }),
    );

    const upload = async (token: string, title: string, fields: Record<string, string>) => {
      const doc = await api.ok(
        `upload ${title}`,
        api.call('POST', '/documents', {
          token,
          multipart: {
            file: { name: `${title}.md`, mimeType: 'text/markdown', buffer: sopMarkdown(title, run) },
            title,
            ...fields,
          },
        }),
      );
      return { id: doc.id as string, title };
    };
    // Fresh tokens: the publisher rows were written after the sessions above were issued.
    const wsPub = await api.switchTo(await api.login(email('wsPub'), PLAN.wsPub.name), workspaceId);
    const alphaPub = await api.switchTo(await api.login(email('alphaPub'), PLAN.alphaPub.name), workspaceId);
    const company = await upload(wsPub.token, `E2E Company Policy ${run}`, { visibility: 'WORKSPACE', preparedBy: 'HR office' });
    const alpha = await upload(alphaPub.token, `E2E Alpha SOP ${run}`, {
      visibility: 'DEPARTMENTS',
      departmentIds: departments.alpha,
    });

    const world: World = {
      run,
      workspaceId,
      workspaceName: `E2E ${run}`,
      departments,
      personas,
      docs: { company, alpha },
    };
    saveWorld(world);
  } finally {
    await api.dispose();
  }
}
