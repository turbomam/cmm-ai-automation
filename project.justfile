## Add your own just recipes here. This is imported by the main justfile.

# Download all tabs from BER CMM Google Sheet as TSV files to data/private/
download-sheets:
  uv run download-sheets

# Download specific tab(s) from Google Sheet
download-sheet tab:
  uv run download-sheets --tabs {{tab}}
