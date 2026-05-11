# AI Workflows

This project supports AI-assisted deckbuilding in two different ways: manual assistant workflows today, and optional API provider workflows later.

## Manual AI Workflow

This is available now and does not require API billing.

1. Generate a local deck build with `mtg-collection build`.
2. Open the generated Markdown prompt.
3. Paste it into Codex, Claude Code, ChatGPT, Claude, or another assistant.
4. Ask for a refined deck JSON in the same format.
5. Save the refined JSON in `data/output/`.
6. Compare and review it with `mtg-collection review --compare-to ...`.
7. Export or render it when you are happy with the result.

When the deck builder creates a deck, the generated HTML viewer already includes draft quality notes and validation results.

Example:

```bash
mtg-collection build \
  --commander "Jhoira of the Ghitu" \
  --name jhoira \
  --theme "suspend big spells"
```

This creates `data/output/jhoira_ai_prompt.md`.

After an assistant returns a refined deck file, a typical follow-up is:

```bash
mtg-collection review \
  --deck data/output/jhoira_refined_deck.json \
  --compare-to data/output/jhoira_deck.json
```

You can also ask the local tuner for non-AI swap ideas before or after the assistant pass:

```bash
mtg-collection review --deck data/output/jhoira_deck.json
```

If you did not install the `mtg-*` commands, use:

```bash
python src/build_commander_deck.py \
  --commander "Jhoira of the Ghitu" \
  --collection data/output/collection_enriched.csv \
  --name jhoira \
  --theme "suspend big spells"
```

## API-Based AI Workflow

This is planned, not implemented.

API-based generation would let the project call a model provider directly. That would usually require:

- a provider account
- an API key
- separate API billing

Normal ChatGPT or Claude subscriptions usually do not include API usage.

The project now has provider scaffolding in `src/deck_providers.py`, but only the `local` provider is implemented. The `openai`, `anthropic`, `openrouter`, and `ollama` names are reserved extension points.

Current provider option:

```bash
--provider local
```

Reserved future provider names:

```bash
--provider openai
--provider anthropic
--provider openrouter
--provider ollama
```

## Recommended Provider Design

Provider integrations should be small adapters around the same local data flow:

```text
enriched collection
  -> local candidate pool
  -> provider adapter
  -> deck JSON
  -> validator
  -> viewer
```

The local candidate pool should be filtered before sending anything to a provider. That keeps prompts smaller, cheaper, and more private.

## User Experience Rules For Future API Features

- Local generation must remain the default.
- API use must be opt-in.
- The command should say which provider is being used.
- The docs should say that provider usage may cost money.
- API keys should come from environment variables.
- Generated files should not contain API keys.
- The project should validate AI output before rendering or recommending it.
