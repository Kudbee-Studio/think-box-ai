# PR #289 — Git Repository Integration

**Goal:** Enable users to paste Git repository URLs directly into the terminal, clone repos, browse files in the dashboard, and save generated files as a workspace.

## Architecture

The Git integration works in three layers:

### 1. Backend (TypeScript/Node)

**git-repo-manager.ts** — Core repository management
- Clone repositories with shallow clone support
- Sync with remote (fetch/pull)
- Build file trees with configurable depth
- Read/write files with security checks (path traversal prevention)
- Track repository state (dirty status, file count, etc.)

**git-api-routes.ts** — REST API endpoints
- `POST /api/git/clone` — Clone a repository
- `GET /api/git/repos` — List all repositories
- `GET /api/git/tree?repo=name` — Get file tree for repository
- `GET /api/git/file?path=...` — Read file content
- `POST /api/git/save` — Save file to workspace
- `GET /api/git/status?repo=name` — Get repository status
- `DELETE /api/git/repos/:name` — Delete repository

### 2. Frontend (JavaScript)

**git-integration.js** — Dashboard UI integration
- **Git URL Detection:** Paste detection and `/git` command parsing
- **Clone Dialog:** User-friendly clone interface with branch/depth options
- **File Tree Sync:** Renders cloned repositories in the existing file tree
- **File Editor:** Modal editor for viewing and editing files
- **Generated Files Section:** Displays files created by the agent
- **Event Integration:** Listens for `agent:file-created` and `agent:file-modified` events

### 3. Styling

**git-integration.css** — Professional UI components
- Clone dialog with progress animation
- Repository sections in file tree
- File editor with syntax highlighting
- Notifications for user feedback

## User Experience

### Workflow 1: Paste Git URL

```
User pastes: https://github.com/owner/repo.git

↓

Dialog appears:
- URL prefilled
- Branch selector
- Shallow clone option

↓

User clicks "Clone"

↓

Files appear in left sidebar under [repo-name]
```

### Workflow 2: Browse and Edit Files

```
User clicks file in tree

↓

File editor modal opens with:
- Syntax highlighting
- Full content display
- Edit capability

↓

User edits and clicks "Save"

↓

File saved to workspace
```

### Workflow 3: Agent Generates Files

```
Agent creates file

↓

Event emitted: window.dispatchEvent(new CustomEvent('agent:file-created', {
  detail: { path: 'output/file.js', content: '...' }
}))

↓

File appears in [Generated] section with:
- ✨ Icon (generated marker)
- Language badge
- Editable content

↓

User can view or export
```

## Implementation Details

### Repository State Tracking

```typescript
interface RepositoryState {
  url: string;
  name: string;
  localPath: string;
  branch: string;
  lastSync: number;
  fileCount: number;
  isDirty: boolean;
  status: 'idle' | 'cloning' | 'syncing' | 'error';
  error?: string;
}
```

### File Tree Structure

```typescript
interface FileTreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  modified?: number;
  children?: FileTreeNode[];
}
```

### Security Considerations

1. **Path Traversal Prevention**
   - Normalize all file paths
   - Reject paths containing `..`
   - Validate against workspace root

2. **Git Clone Limits**
   - Shallow clone by default (faster, smaller)
   - Optional depth parameter
   - Configurable workspace directory

3. **File Access Control**
   - Read-only for repository files by default
   - Write only to workspace directory
   - No access to parent directories

## Integration with Existing Systems

### File Tree Display

The Git integration extends the existing file tree (`#file-tree` element) by adding:
- Repository sections with collapsible trees
- Generated files section
- Language-specific badges
- File metadata (size, modification time)

### Terminal Commands

The integration hooks into the terminal input to enable:
- `/git https://github.com/owner/repo.git` — Clone repository
- `Cmd/Ctrl+V` with Git URL — Auto-detect and clone

### Agent File Creation

The agent system can emit files via:
```javascript
window.dispatchEvent(new CustomEvent('agent:file-created', {
  detail: {
    path: 'output/generated.js',
    content: '// Generated code\nfunction hello() { ... }',
    language: 'javascript'
  }
}));
```

## API Endpoints

### Clone Repository
```
POST /api/git/clone
{
  "url": "https://github.com/owner/repo.git",
  "branch": "main",
  "shallow": true
}

Response:
{
  "url": "https://github.com/owner/repo.git",
  "name": "repo",
  "localPath": "./workspaces/repo",
  "branch": "main",
  "lastSync": 1695123456789,
  "fileCount": 1234,
  "isDirty": false,
  "status": "idle"
}
```

### Get File Tree
```
GET /api/git/tree?repo=repo

Response:
{
  "name": "repo",
  "path": "./workspaces/repo",
  "type": "directory",
  "children": [
    {
      "name": "src",
      "path": "./workspaces/repo/src",
      "type": "directory",
      "children": [ ... ]
    },
    {
      "name": "README.md",
      "path": "./workspaces/repo/README.md",
      "type": "file",
      "size": 1024,
      "modified": 1695123456789
    }
  ]
}
```

### Read File
```
GET /api/git/file?path=./workspaces/repo/src/index.js

Response:
{
  "content": "// File content here",
  "language": "javascript"
}
```

### Save File
```
POST /api/git/save
{
  "path": "./workspaces/repo/src/index.js",
  "content": "// Updated content"
}

Response:
{
  "success": true,
  "path": "./workspaces/repo/src/index.js",
  "size": 1024
}
```

## Features

### File Operations
- ✅ Clone repositories (shallow/full)
- ✅ Browse file trees with collapsible directories
- ✅ Read file content with syntax highlighting
- ✅ Save/edit files in workspace
- ✅ View file metadata (size, modification time)
- ✅ Detect language for syntax highlighting

### Repository Management
- ✅ Track repository state (clean/dirty)
- ✅ List all cloned repositories
- ✅ Delete repositories
- ✅ Sync with remote (fetch/pull)
- ✅ Support multiple branches

### User Interface
- ✅ Git URL detection on paste
- ✅ Clone dialog with options
- ✅ File tree integration
- ✅ File editor modal
- ✅ Syntax highlighting
- ✅ Language-specific badges
- ✅ Generated files section
- ✅ Notifications for user feedback

### Security
- ✅ Path traversal prevention
- ✅ Shallow clone by default
- ✅ Workspace isolation
- ✅ Git operation error handling

## Supported Languages

The integration auto-detects and provides syntax highlighting for:
- JavaScript/TypeScript/JSX/TSX
- Python, Java, Go, Rust, C++, C#, Ruby, PHP, Swift, Kotlin
- SQL, HTML, CSS, JSON, YAML, Markdown, Bash

## Future Enhancements

1. **Diff Viewer** — Show changes between versions
2. **Commit History** — Browse commit log
3. **Blame View** — See who changed each line
4. **Branch Switching** — Switch between branches
5. **Search** — Full-text search across files
6. **Export** — Download cloned repository as zip
7. **Merge Conflicts** — Visual conflict resolution
8. **Git Operations** — Commit, push, pull from dashboard
9. **GitHub Integration** — PR/Issue linking
10. **AI Code Review** — Analyze code with Think Tokens

## Testing Strategy

### Unit Tests
- Repository cloning with various URLs
- File tree generation
- Path traversal prevention
- Language detection

### Integration Tests
- Clone real repositories
- File tree rendering
- File editor operations
- Generated file tracking

### E2E Tests
- Complete workflow: paste URL → browse → edit → save
- Multiple repositories
- Large file handling
- Error recovery

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Clone time | < 5s | Shallow clone, typical repo |
| File tree render | < 500ms | 1000+ files |
| File read | < 100ms | < 1MB file |
| File save | < 200ms | Network write |
| Search | < 1s | Full-text search |

## Commit Message

```
feat(git-integration): clone and manage Git repos in dashboard

- Add GitRepoManager for clone, sync, file tree operations
- Create Git REST API endpoints (/api/git/*)
- Build dashboard Git integration with URL detection
- Support paste detection for GitHub URLs
- File editor with syntax highlighting by language
- Generated files tracking in [Generated] section
- Security: prevent path traversal, shallow clone by default
- Styling: modals, file tree expansion, notifications
- Language detection for 20+ programming languages

This enables users to:
1. Paste GitHub URL → auto-clone to workspace
2. Browse files in left sidebar with full tree view
3. Edit files with syntax highlighting
4. View files created by the agent in [Generated] section
5. All workspace files synced to SQLite for persistence

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

**Status:** Ready for testing and review
**Files:** 5 new modules + updated index.html
**Lines:** ~1500 TS/JS + ~300 CSS + ~500 docs
