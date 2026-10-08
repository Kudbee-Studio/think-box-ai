// Job templates: ready goals for common repository jobs. A template only fills the goal box; the person reads it and presses run, so nothing starts by itself.
// Every goal is written for what a normal run can do (list, read and write files in the chosen repository) and says so: it cannot run code, tests or git, and must list what it could not verify.
export interface JobTemplate {
  id: string; name: string; description: string;
  /** Needs a repository chosen with "Use for agent". */
  needs_repo: true;
  param?: { key: string; label: string; placeholder: string; required: boolean };
  goal: (input: string) => string;
}

const LIMITS = 'You can only list, read and write files in this repository. You cannot run code, tests or git, so never say that anything passes or works. Finish with a short list headed "Could not verify" of what a person should check.';
const MAX_INPUT = 300;
/** One line, no control characters, capped: the input is a description for the agent, not a way to reshape the goal. */
const clean = (s: string): string => s.replace(/[\u0000-\u001f\u007f]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, MAX_INPUT);

export const JOB_TEMPLATES: JobTemplate[] = [
  { id: 'explain-codebase', name: 'Explain this codebase', description: 'Reads the repository and writes ARCHITECTURE.md: what it does, how it is laid out, where to start.', needs_repo: true,
    goal: () => `Read this repository (start with list_files, then the README, the package or build files and the main entry points) and write ARCHITECTURE.md: what the project does, how the folders are laid out, the main flows, and where a new contributor should start. Only describe what you actually read. ${LIMITS}` },
  { id: 'find-todos', name: 'Collect TODOs and FIXMEs', description: 'Finds TODO/FIXME notes and writes TODO-REPORT.md grouped by file, without changing any code.', needs_repo: true,
    goal: () => `Go through the source files in this repository with list_files and read_file and collect every TODO, FIXME and HACK comment. Write TODO-REPORT.md grouped by file, with the line text and a one-line note on how urgent each looks. Do not change any other file. ${LIMITS}` },
  { id: 'review-bugs', name: 'Review for bugs', description: 'Reads a file or folder (or the whole repository) and writes REVIEW.md listing likely bugs, without editing code.', needs_repo: true,
    param: { key: 'area', label: 'File or folder', placeholder: 'src/ (leave empty for the whole repository)', required: false },
    goal: (a) => `Review ${a ? `"${a}"` : 'the source files'} in this repository for likely bugs: wrong conditions, unhandled errors, off-by-one mistakes, missing input checks. Write REVIEW.md with each finding as file, line, what is wrong and a suggested fix. Do not edit the code itself. ${LIMITS}` },
  { id: 'fix-bug', name: 'Fix a bug', description: 'Describe the bug; the agent finds the cause and edits the code. Review the result in Files > Changes.', needs_repo: true,
    param: { key: 'bug', label: 'What is wrong', placeholder: 'Pagination shows one page too few when the count divides evenly', required: true },
    goal: (b) => `There is a bug in this repository: ${b}. Find the cause by reading the code, make the smallest change that fixes it, and explain what you changed and why in CHANGES.md. Do not reformat or rewrite unrelated code. ${LIMITS}` },
  { id: 'add-docs', name: 'Document a file', description: 'Adds clear doc comments to a file without changing what the code does.', needs_repo: true,
    param: { key: 'file', label: 'File', placeholder: 'src/cart.js', required: true },
    goal: (f) => `Read "${f}" in this repository and add short, accurate doc comments to its functions and exported items. Do not change any code, only add comments, and describe only what the code really does. ${LIMITS}` },
  { id: 'write-tests', name: 'Write tests for a file', description: 'Writes a test file for a module, in the style the repository already uses. The tests are not run.', needs_repo: true,
    param: { key: 'file', label: 'File', placeholder: 'src/slug.js', required: true },
    goal: (f) => `Read "${f}" in this repository, look at how existing tests are written, and write a new test file for it in the same style covering normal use, edge cases and errors. Do not change "${f}" itself. Because you cannot run them, say plainly that the tests have not been run. ${LIMITS}` },
];

export function fillGoal(id: string, input?: string): { ok: true; goal: string } | { ok: false; error: string } {
  const t = JOB_TEMPLATES.find((x) => x.id === id);
  if (!t) return { ok: false, error: 'Unknown template' };
  const value = clean(input ?? '');
  if (t.param?.required && !value) return { ok: false, error: `${t.param.label} is required` };
  return { ok: true, goal: t.goal(value) };
}
