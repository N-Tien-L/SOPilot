import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

export const PERSONA_KEYS = [
  'owner',
  'admin',
  'wsPub',
  'alphaPub',
  'alphaMember',
  'betaMember',
  'loner',
  'spareA',
  'spareB',
] as const;
export type PersonaKey = (typeof PERSONA_KEYS)[number];

export interface Persona {
  key: PersonaKey;
  email: string;
  name: string;
  userId: string;
}

/**
 * What global-setup built, written to `.world.json` so every spec sees the same workspace.
 *
 * - owner: OWNER, not a publisher (the workspace publisher role moved to wsPub)
 * - admin: ADMIN, no department
 * - wsPub: MEMBER without department, the workspace publisher
 * - alphaPub / alphaMember: MEMBER of Alpha; alphaPub publishes for Alpha
 * - betaMember: MEMBER of Beta
 * - loner: MEMBER without department
 * - spareA / spareB: MEMBER without department; the specs that move people around use only these
 */
export interface World {
  run: string;
  workspaceId: string;
  workspaceName: string;
  departments: { alpha: string; beta: string };
  personas: Record<PersonaKey, Persona>;
  docs: { company: { id: string; title: string }; alpha: { id: string; title: string } };
}

const FILE = join(__dirname, '..', '.world.json');

export function saveWorld(world: World): void {
  writeFileSync(FILE, JSON.stringify(world, null, 2));
}

export function loadWorld(): World {
  if (!existsSync(FILE)) throw new Error('No .world.json: global-setup did not run (is the stack up?)');
  return JSON.parse(readFileSync(FILE, 'utf8')) as World;
}

export function clearWorld(): void {
  if (existsSync(FILE)) writeFileSync(FILE, '{}');
}
