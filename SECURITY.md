# Security And Privacy Policy

This project handles local collection files. Those files may reveal a user's card collection, spending history, pricing data, or deckbuilding preferences.

## Supported Versions

This project is early-stage. Please report issues against the current `main` branch unless releases are introduced later.

## Reporting A Privacy Or Security Issue

If you find a problem, please open a GitHub issue if it is safe to discuss publicly.

If the issue includes private collection data, API keys, credentials, or another person's personal information, do not paste that data into a public issue. Instead, contact the repository maintainer privately if contact information is available on the repository profile.

## What Counts As Important

Please report:

- real collection data accidentally committed to the repository
- generated files that include private collection contents
- scripts that write outside the requested output path
- unsafe handling of future API keys
- docs that could lead users to publish private collection files by mistake

## API Keys

The current project does not require API keys.

Future API-based AI features should:

- be opt-in
- read keys from environment variables
- never write keys to generated files
- never commit keys to Git
- clearly explain that provider API usage may cost money
