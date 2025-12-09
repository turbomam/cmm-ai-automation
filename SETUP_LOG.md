# Setup Log: cmm-ai-automation

This document records the setup process and design decisions for the `cmm-ai-automation` repository.

**Date:** 2024-12-09
**Author:** Mark Miller (with Claude Code assistance)
**Repository:** https://github.com/turbomam/cmm-ai-automation

---

## 1. Project Goals

Create a GitHub repository for AI-assisted automation of Critical Mineral Metabolism (CMM) data curation with:
- Python-based tools using LinkML and OBO Foundry ecosystem
- Integration with private Google Sheets (specifically "BER CMM Data for AI - for editing")
- AI/LLM automation via GitHub Actions (Claude Code)

### Collaboration with CultureBotAI/CMM-AI

This repository is developed in collaboration with [CultureBotAI/CMM-AI](https://github.com/CultureBotAI/CMM-AI). The division of responsibilities:

| Repository | Focus |
|------------|-------|
| [CultureBotAI/CMM-AI](https://github.com/CultureBotAI/CMM-AI) | AI-driven biological discovery, microorganism identification, analysis workflows |
| [turbomam/cmm-ai-automation](https://github.com/turbomam/cmm-ai-automation) | Data modeling (LinkML), Google Sheets integration, OBO Foundry ontology tooling |

The AI automation workflows in this repository were adapted from those used in CMM-AI, which in turn came from the [ai4curation/github-ai-integrations](https://github.com/ai4curation/github-ai-integrations) template maintained by the Monarch Initiative.

---

## 2. Template Selection

### Evaluated Options

| Template | Tool | Pros | Cons |
|----------|------|------|------|
| [linkml-project-cookiecutter](https://github.com/linkml/linkml-project-cookiecutter) | cruft | Official LinkML, well-maintained | Uses Poetry, older approach |
| [linkml-project-copier](https://github.com/dalito/linkml-project-copier) | copier | Uses `uv`, modern, based on cookiecutter | Newer, fewer users |
| [ontology-development-kit (ODK)](https://github.com/INCATools/ontology-development-kit) | Docker/Make | Full ontology lifecycle | Overkill for this use case |
| [ai4curation/github-ai-integrations](https://github.com/ai4curation/github-ai-integrations) | copier | Claude GitHub Actions, MCP servers | AI-only, no schema support |

### Decision

Use **linkml-project-copier** as the base template, then layer on **ai4curation/github-ai-integrations** for AI automation.

**Rationale:**
- `uv` is faster and simpler than Poetry for dependency management
- LinkML provides schema-driven data modeling appropriate for structured CMM data
- The ai4curation template provides battle-tested Claude GitHub Actions with MCP server integration (OLS for ontology lookup)

---

## 3. Repository Creation

### 3.1 Create Empty GitHub Repo

```bash
gh repo create turbomam/cmm-ai-automation --public \
  --description "AI-assisted automation for Critical Mineral Metabolism data curation using LinkML, OBO tools, and Google Sheets integration"
```

**Result:** https://github.com/turbomam/cmm-ai-automation

### 3.2 Clone Locally

```bash
cd /home/mark/gitrepos
gh repo clone turbomam/cmm-ai-automation
# Warning: empty repository
```

---

## 4. Initialize with LinkML Template

### 4.1 Install Dependencies

```bash
pip install copier jinja2-time
```

Note: `jinja2-time` was required as an additional dependency for the copier template.

### 4.2 Run Copier

```bash
copier copy --trust --defaults gh:dalito/linkml-project-copier cmm-ai-automation \
  --data project_name="cmm-ai-automation" \
  --data project_description="AI-assisted automation for Critical Mineral Metabolism data curation" \
  --data full_name="Mark Miller" \
  --data email="MAM@lbl.gov" \
  --data github_org="turbomam" \
  --data main_schema_class="CmmDataset" \
  --data license="MIT"
```

### 4.3 Template Output Structure

```
cmm-ai-automation/
├── .github/
│   ├── dependabot.yml
│   └── workflows/
│       ├── deploy-docs.yaml
│       ├── main.yaml
│       ├── pypi-publish.yaml
│       └── test_pages_build.yaml
├── docs/
├── examples/
├── project/
├── src/cmm_ai_automation/
│   ├── schema/cmm_ai_automation.yaml  # LinkML schema
│   └── datamodel/                      # Generated Python classes
├── tests/
├── pyproject.toml
├── justfile
└── mkdocs.yml
```

### 4.4 Initial Commit

```bash
cd /home/mark/gitrepos/cmm-ai-automation
git init
git add -A
git commit -m "Initialize from linkml-project-copier template"
git branch -m main
git remote add origin git@github.com:turbomam/cmm-ai-automation.git
```

---

## 5. Add AI Automation (Claude GitHub Actions)

### 5.1 Source Analysis

Examined [CultureBotAI/CMM-AI](https://github.com/CultureBotAI/CMM-AI) `.github/` directory, which uses the [ai4curation/github-ai-integrations](https://github.com/ai4curation/github-ai-integrations) copier template.

**Files identified:**
- `workflows/claude.yml` - Main Claude Code action
- `workflows/claude-issue-triage.yml` - Auto-triage issues
- `workflows/claude-issue-summarize.yml` - Auto-summarize issues
- `copilot-setup-steps.yml` - GitHub Copilot workspace setup
- `ai-controllers.json` - List of GitHub users who can control Claude
- `actions/` - Custom composite actions

### 5.2 Download Workflow Files

```bash
# Create directories
mkdir -p .github/actions

# Download workflows
gh api repos/ai4curation/github-ai-integrations/contents/template/.github/workflows/claude.yml | \
  jq -r '.content' | base64 -d > .github/workflows/claude.yml

gh api repos/ai4curation/github-ai-integrations/contents/template/.github/workflows/claude-issue-triage.yml | \
  jq -r '.content' | base64 -d > .github/workflows/claude-issue-triage.yml

gh api repos/ai4curation/github-ai-integrations/contents/template/.github/workflows/claude-issue-summarize.yml | \
  jq -r '.content' | base64 -d > .github/workflows/claude-issue-summarize.yml

gh api repos/ai4curation/github-ai-integrations/contents/template/.github/copilot-setup-steps.yml | \
  jq -r '.content' | base64 -d > .github/copilot-setup-steps.yml
```

### 5.3 Download Custom Actions

```bash
mkdir -p .github/actions/claude-code-action \
         .github/actions/claude-issue-summarize-action \
         .github/actions/claude-issue-triage-action

# Download action.yml for each
curl -sL "https://raw.githubusercontent.com/ai4curation/github-ai-integrations/main/template/.github/actions/claude-code-action/action.yml" \
  -o ".github/actions/claude-code-action/action.yml"

curl -sL "https://raw.githubusercontent.com/ai4curation/github-ai-integrations/main/template/.github/actions/claude-issue-summarize-action/action.yml" \
  -o ".github/actions/claude-issue-summarize-action/action.yml"

curl -sL "https://raw.githubusercontent.com/ai4curation/github-ai-integrations/main/template/.github/actions/claude-issue-triage-action/action.yml" \
  -o ".github/actions/claude-issue-triage-action/action.yml"
```

### 5.4 Create AI Controllers Config

```bash
echo '["turbomam"]' > .github/ai-controllers.json
```

This restricts Claude action triggers to the `turbomam` GitHub user.

### 5.5 Claude Workflow Features

The `claude.yml` workflow includes:

```yaml
# Triggers on @claude mentions in:
# - Issue comments
# - PR review comments
# - PR reviews
# - New issues (title or body)

# MCP Servers configured:
mcp_config: |
  {
    "mcpServers": {
      "ols": {
        "command": "uvx",
        "args": ["ols-mcp"]
      },
      "sequential-thinking": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
      }
    }
  }

# Allowed tools:
allowed_tools: "Bash(*),FileEdit,Edit,MultiEdit,WebSearch,WebFetch,mcp__ols_mcp__search_all_ontologies,mcp__ols_mcp__get_terms_from_ontology"
```

---

## 6. Add Google Sheets Integration

### 6.1 Design Decision: gspread vs google-api-python-client

| Library | Pros | Cons |
|---------|------|------|
| `gspread` | Simple API, pandas integration | Less control |
| `google-api-python-client` | Full API access | More verbose |

**Decision:** Use `gspread` for simplicity, with `google-auth` for authentication.

### 6.2 Add Dependencies

Updated `pyproject.toml`:

```toml
dependencies = [
  "linkml-runtime >=1.9.4",
  "gspread >=6.0.0",
  "google-auth >=2.0.0",
  "google-auth-oauthlib >=1.0.0",
  "pandas >=2.0.0",
]
```

### 6.3 Create gsheets Module

Created `src/cmm_ai_automation/gsheets.py` with:

- `get_gspread_client()` - Authenticate with service account
- `get_spreadsheet()` - Open spreadsheet by name or ID
- `list_worksheets()` - List all tabs in a spreadsheet
- `get_sheet_data()` - Read worksheet to DataFrame
- `update_sheet_data()` - Write DataFrame to worksheet

**Known Spreadsheet IDs:**
```python
KNOWN_SHEETS = {
    "BER CMM Data for AI - for editing": "1h-kOdyvVb1EJPqgTiklTN9Z8br_8bP8KGmxA19clo7Q",
}
```

### 6.4 Authentication Strategy

The module supports three credential locations (in order of precedence):
1. Explicit path passed to functions
2. `GOOGLE_APPLICATION_CREDENTIALS` environment variable
3. Default gspread location: `~/.config/gspread/service_account.json`

---

## 7. Documentation Updates

Updated `README.md` with:
- Feature list
- Quick start guide
- Google Sheets usage examples
- AI integration documentation

---

## 8. Final Commit and Push

```bash
git add -A
git commit -m "Add AI automation and Google Sheets integration

- Add Claude Code GitHub Action workflows from ai4curation/github-ai-integrations
  - claude.yml: Main Claude Code action for @claude mentions
  - claude-issue-triage.yml: Auto-triage new issues
  - claude-issue-summarize.yml: Auto-summarize issues
- Add custom actions for Claude integrations
- Add copilot-setup-steps.yml for GitHub Copilot workspace
- Add gsheets.py module for Google Sheets API access
- Add gspread, google-auth, pandas dependencies
- Update README with features, quick start, and usage examples"

git push -u origin main
```

---

## 9. Post-Setup Configuration Required

### 9.1 GitHub Repository Secrets

| Secret | Purpose |
|--------|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Authentication for Claude GitHub Action |
| `GOOGLE_CREDENTIALS_JSON` | (Optional) Service account JSON for CI/CD |

### 9.2 Google Cloud Setup

1. Create a Google Cloud project
2. Enable Google Sheets API and Google Drive API
3. Create a service account
4. Download JSON key file
5. Share the "BER CMM Data for AI - for editing" spreadsheet with the service account email

### 9.3 Local Development

```bash
cd /home/mark/gitrepos/cmm-ai-automation

# Initialize project
just setup

# Set credentials
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json

# Or copy to default location
cp /path/to/service_account.json ~/.config/gspread/service_account.json
```

---

## 10. Planned Integrations

### Knowledge Graph and Ontology Resources

| Project | Purpose | Integration Status |
|---------|---------|-------------------|
| [kg-microbe](https://github.com/Knowledge-Graph-Hub/kg-microbe) | Microbial knowledge graph with strain/function data | Planned - CMM strains link via `kg_node_ids` column |
| [kgx](https://github.com/biolink/kgx) | Knowledge Graph Exchange for Biolink Model graphs | Planned - Import/export KG data |
| [biolink-model](https://github.com/biolink/biolink-model) | Schema and upper ontology for biological KGs | Planned - Data modeling alignment |
| [biolink-model-toolkit](https://github.com/biolink/biolink-model-toolkit) | Python utilities for Biolink Model | Planned - Model validation |
| [metpo](https://github.com/berkeleybop/metpo) | Microbial Phenotype Ontology | Planned - Phenotype annotation |

See also: [biolink organization](https://github.com/orgs/biolink/repositories) for additional tools (ontobio, etc.).

### Data Flow

```
Google Sheets (BER CMM Data)
    ↓
cmm-ai-automation (this repo)
    ↓ LinkML schema validation
    ↓ Ontology term lookup (OLS)
    ↓
kg-microbe (knowledge graph)
    ↓ kgx export
    ↓
Biolink Model-compliant KG
```

---

## 11. References

- [linkml-project-copier](https://github.com/dalito/linkml-project-copier) - Base template
- [ai4curation/github-ai-integrations](https://github.com/ai4curation/github-ai-integrations) - AI automation template
- [CultureBotAI/CMM-AI](https://github.com/CultureBotAI/CMM-AI) - Collaborating project for CMM discovery
- [kg-microbe](https://github.com/Knowledge-Graph-Hub/kg-microbe) - Microbial knowledge graph
- [biolink organization](https://github.com/orgs/biolink/repositories) - Biolink Model ecosystem
  - [kgx](https://github.com/biolink/kgx) - Knowledge Graph Exchange tools
  - [biolink-model](https://github.com/biolink/biolink-model) - Schema and upper ontology
  - [biolink-model-toolkit](https://github.com/biolink/biolink-model-toolkit) - Python utilities
- [metpo](https://github.com/berkeleybop/metpo) - Microbial Phenotype Ontology
- [gspread documentation](https://docs.gspread.org/)
- [LinkML documentation](https://linkml.io/)
- [Claude Code GitHub Action](https://github.com/anthropics/claude-code-action)
