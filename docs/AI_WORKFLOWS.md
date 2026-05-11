# AI Workflows

The project supports two AI-assisted workflows.

## Manual Assistant Workflow

This does not require API billing.

1. Build a local deck:

   ```bash
   mtg-collection build --commander "Jhoira of the Ghitu" --theme "suspend big spells"
   ```

2. Open the generated `<deck_name>_ai_prompt.md` file in the deck folder under `data/output/`.
3. Paste it into Codex, Claude Code, ChatGPT, Claude, or another assistant.
4. Ask for a refined deck JSON in the same format.
5. Save the refined JSON in `data/output/`.
6. Review the changes:

   ```bash
   mtg-collection review \
     --deck data/output/jhoira_refined/jhoira_refined_deck.json \
     --compare-to data/output/jhoira_of_the_ghitu_suspend_big_spells/jhoira_of_the_ghitu_suspend_big_spells_deck.json
   ```

## OpenAI API Provider

This lets the project call OpenAI directly. It is opt-in and may cost money.

Set an API key:

```bash
export OPENAI_API_KEY=your_api_key_here
```

Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="your_api_key_here"
```

Then run:

```bash
mtg-collection build \
  --commander "Jhoira of the Ghitu" \
  --theme "suspend big spells" \
  --provider openai
```

Optional model selection:

```bash
mtg-collection build \
  --commander "Jhoira of the Ghitu" \
  --provider openai \
  --model gpt-5.2
```

You can also set:

```bash
export OPENAI_MODEL=gpt-5.2
```

The OpenAI provider first builds the local draft, sends a focused candidate pool and draft prompt to OpenAI, expects deck JSON back, then runs the normal validation and viewer workflow.

## What Gets Sent

The OpenAI request includes:

- commander details
- the local draft deck JSON
- selected candidate cards from the enriched collection
- theme hint, if provided

It does not intentionally send your raw ManaBox CSV, but the candidate pool can still reveal cards you own. Use the local or manual workflow if you do not want collection-derived data sent to an API provider.

## Current Providers

Available today:

- `local`
- `openai`

Reserved for future work:

- `anthropic`
- `openrouter`
- `ollama`

Normal ChatGPT or Claude subscriptions usually do not include API usage. API providers require separate API keys and billing.
