# Contract with the web app

`types.schema.json` is the JSON Schema of every type the web app reads from the API, generated from `src/lib/types.ts` and the response types declared in `src/lib/api.ts` (entry point: `web-types.ts`). `test_contract_web_types.py` validates every endpoint's response against it, with extra properties refused, so a renamed or added field fails on whichever side changed first.

Regenerate after changing a type the API returns, and commit the result:

```bash
npm run contract:generate
uv run pytest backend/tests/contract
```

CI regenerates it (`.github/workflows/web.yml`) and fails if the committed file is stale.
