<a href="https://github.com/dalito/linkml-project-copier"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-teal.json" alt="Copier Badge" style="max-width:100%;"/></a>

# cmm-ai-automation

AI-assisted automation for Critical Mineral Metabolism (CMM) data curation using LinkML, OBO Foundry tools, and Google Sheets integration.

## Collaboration

This repository is developed in collaboration with [CultureBotAI/CMM-AI](https://github.com/CultureBotAI/CMM-AI), which focuses on AI-driven discovery of microorganisms relevant to critical mineral metabolism. While CMM-AI handles the biological discovery and analysis workflows, this repository provides:

- Schema-driven data modeling with LinkML
- Integration with private Google Sheets data sources
- OBO Foundry ontology tooling for semantic annotation

## Features

- **LinkML Schema**: Data models for CMM microbial strain data
- **Google Sheets Integration**: Read/write access to private Google Sheets (e.g., BER CMM Data)
- **AI Automation**: GitHub Actions with Claude Code for issue triage, summarization, and code assistance
- **OBO Foundry Tools**: Integration with OLS (Ontology Lookup Service) for ontology term lookup

## Quick Start

```bash
# Clone the repository
git clone https://github.com/turbomam/cmm-ai-automation.git
cd cmm-ai-automation

# Install dependencies with uv
uv sync

# Set up Google Sheets credentials (service account)
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json

# Or place credentials in default location
# ~/.config/gspread/service_account.json
```

## Google Sheets Usage

```python
from cmm_ai_automation.gsheets import get_sheet_data, list_worksheets

# List available tabs in the BER CMM spreadsheet
tabs = list_worksheets("BER CMM Data for AI - for editing")
print(tabs)

# Read data from a specific tab
df = get_sheet_data("BER CMM Data for AI - for editing", "media_ingredients")
print(df.head())
```

## AI Integration

This repo includes GitHub Actions that respond to `@claude` mentions in issues and PRs:
- Issue triage and labeling
- Issue summarization
- Code assistance and PR reviews

Requires `CLAUDE_CODE_OAUTH_TOKEN` secret to be configured.

## Documentation Website

[https://turbomam.github.io/cmm-ai-automation](https://turbomam.github.io/cmm-ai-automation)

## Repository Structure

* [docs/](docs/) - mkdocs-managed documentation
  * [elements/](docs/elements/) - generated schema documentation
* [examples/](examples/) - Examples of using the schema
* [project/](project/) - project files (these files are auto-generated, do not edit)
* [src/](src/) - source files (edit these)
  * [cmm_ai_automation](src/cmm_ai_automation)
    * [schema/](src/cmm_ai_automation/schema) -- LinkML schema
      (edit this)
    * [datamodel/](src/cmm_ai_automation/datamodel) -- generated
      Python datamodel
* [tests/](tests/) - Python tests
  * [data/](tests/data) - Example data

## Developer Tools

There are several pre-defined command-recipes available.
They are written for the command runner [just](https://github.com/casey/just/). To list all pre-defined commands, run `just` or `just --list`.

## Credits

This project uses the template [linkml-project-copier](https://github.com/dalito/linkml-project-copier) published as [doi:10.5281/zenodo.15163584](https://doi.org/10.5281/zenodo.15163584).

AI automation workflows adapted from [ai4curation/github-ai-integrations](https://github.com/ai4curation/github-ai-integrations) (Monarch Initiative).

## Related Projects

- [CultureBotAI/CMM-AI](https://github.com/CultureBotAI/CMM-AI) - AI-driven discovery for critical mineral metabolism research
