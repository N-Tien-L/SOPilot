/** A small but real SOP in Markdown. The run id keeps every upload unique (the server refuses duplicate bytes). */
export function sopMarkdown(title: string, run: string): Buffer {
  return Buffer.from(
    [
      `# ${title}`,
      '',
      `Document code: E2E-${run.toUpperCase()}. Revision 01. Effective date 2026-01-15.`,
      '',
      '## 1. Purpose',
      'This procedure explains how an employee requests leave and how the request is approved.',
      '',
      '## 2. Scope',
      'It applies to every employee of the company who works on a full-time contract.',
      '',
      '## 3. Procedure',
      '1. The employee submits a leave request at least three working days in advance.',
      '2. The line manager approves or rejects the request within two working days.',
      '3. Human Resources records the approved leave in the staff calendar.',
      '',
      '## 4. Records',
      'Approved requests are kept for two years.',
      '',
    ].join('\n'),
    'utf8',
  );
}
