---
name: Gamma clobTokenIds
description: How YES/NO token IDs are encoded in the Gamma API market response
---

## Rule
Token IDs are in the field `clobTokenIds` as a **JSON-encoded string**, not in a `tokens[]` array.

Format: `"[\"<yes_token_id>\", \"<no_token_id>\"]"`  
- Index 0 = YES token  
- Index 1 = NO token

**Why:** The `tokens` array field does not exist in the Gamma API response. All 240 Sprint 7 markets had null token IDs because the code looked for `tokens[]` and always found nothing.

**How to apply:** Use `_extract_clob_token_ids(clob_token_ids: Optional[str])` from `gamma_series_client.py`. In `GammaMarketRaw`, the field is declared as `clob_token_ids: Optional[str] = Field(None, alias="clobTokenIds")`. Parse with `json.loads()` and guard against `JSONDecodeError`, `IndexError`, `TypeError`.
