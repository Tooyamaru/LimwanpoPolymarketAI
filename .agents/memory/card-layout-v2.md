---
name: Market Card Layout V2
description: 4-row card spec with PROFIT replacing REWARD, AI Decision Engine status, 3-col Row 3
---

## Rule
Card layout is now 4 rows:
- Row 1: Asset/TF/movement | UP% / DOWN% (CLOB yes_mid/no_mid)
- Row 2: TARGET (3fr, mc-ptb-v-main) | PROFIT (2fr) — grid-template-columns:3fr 2fr inline
- Row 3: CONF | GAP | SPREAD — grid-template-columns:1fr 1fr 1fr inline
- Bottom: Countdown | STATUS (from AI Decision Engine)

## Key decisions

**PROFIT formula:** `STAKE_DEFAULT(10) / tradePrice - STAKE_DEFAULT`
- Direction BUY_NO → tradePrice = no_mid; else yes_mid
- Direction comes from `_opp.direction` (opportunity engine)
- STAKE_DEFAULT=10 mirrors POSITION_SIZE_MIN_USDC from settings.py

**STATUS priority:** non-active market > open position (ENTRY) > `_dec.decision` (WAIT/READY) > MONITORING
- WAIT = red, READY = green, ENTRY = yellow, MONITORING = cyan
- `decisions{}` global, fetched from GET /api/v1/decision?limit=50, indexed newest-first by condition_id

**CSS:** `.mc-ptb` must NOT have `!important` on grid-template-columns — inline styles in renderCard control each row's column count independently.

**Why:** REWARD (1/yes_mid payout multiplier) was removed in favour of dollar profit estimate. Separate mc-conf-row div removed; CONF merged into 3-col Row 3. mc-conf-row CSS class kept in stylesheet but no longer emitted by renderCard.
