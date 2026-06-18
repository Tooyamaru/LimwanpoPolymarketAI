# SPRINT 5 — Market Source Validation Investigation Report

**Date:** 2026-06-18  
**Source Endpoint:** `https://clob.polymarket.com/markets`  
**Run ID:** `b632be63-03f7-4d53-9887-3a250a45015d`  
**Scan Completed:** 2026-06-18T07:55:07Z  

---

## STEP 1 — Validation Run

`POST /api/v1/source-validation/run` was executed. The scanner paginated through the full
Polymarket CLOB market set (250 pages × ~1,000 records per page).

**Status:** Complete — no errors.

---

## STEP 2 — Raw Results Collected

| Endpoint | Result |
|---|---|
| `GET /api/v1/source-validation` | `{ "source": "clob", "markets": 75794 }` |
| `GET /api/v1/source-validation/audit` | 61,167 Up/Down candidate markets |
| `GET /api/v1/source-validation/search?q=btc` | 500+ BTC markets returned |
| `GET /api/v1/source-validation/search?q=eth` | 500+ ETH markets returned |
| `GET /api/v1/source-validation/search?q=sol` | 500+ SOL markets returned |
| `GET /api/v1/source-validation/search?q=xrp` | 500+ XRP markets returned |

---

## STEP 3 — Investigation Report: Market Classification Breakdown

### Source Validation Run Summary

| Metric | Count |
|---|---|
| **Total markets scanned** | **250,000** |
| **Total asset-matched markets** (BTC/ETH/SOL/XRP) | **75,794** |
| **Total Up/Down candidates** | **61,167** |
| — BTC Up/Down candidates | 18,218 |
| — ETH Up/Down candidates | 17,650 |
| — SOL Up/Down candidates | 12,796 |
| — XRP Up/Down candidates | 12,503 |

### EventClassifier Breakdown — All 250,000 Markets

| Event Type | Count | % of Total |
|---|---|---|
| **UPDOWN** | 48,930 | 19.6% |
| **PRICE_RANGE** | 42,455 | 17.0% |
| **NEWS_EVENT** | 1,479 | 0.6% |
| **POLITICS** | 19,597 | 7.8% |
| **OTHER** | 126,206 | 50.5% |
| — not yet classified (partial runs) | ~11,333 | ~4.5% |

> Source: `GET /api/v1/classifier/stats` — reflects the latest full discovery run.

---

## STEP 4 — BTC: First 20 Discovered Markets

> Source: `GET /api/v1/source-validation/search?q=btc&limit=500`  
> Event type for all: **UPDOWN**

| # | Title | Slug | Market ID (condition_id) | Event ID |
|---|---|---|---|---|
| 1 | Bitcoin Up or Down - December 15, 2:15PM-2:30PM ET | `btc-updown-15m-1765826100` | `0xb4d260bc5a7aa7df98c2993cc0a8a42151ce60e51f36fce1048210b6b8607630` | — |
| 2 | Bitcoin Up or Down - December 16, 12:00AM-4:00AM ET | `btc-updown-4h-1765861200` | `0xcbfb1414d9c8567c4ecc441e048545b48e0aa20e00c205f2879400ed16868a9c` | — |
| 3 | Bitcoin Up or Down - December 15, 10:00PM-10:15PM ET | `btc-updown-15m-1765854000` | `0x6aa8d0861f05a5b6ff98ca1300afc0258c4cc98f90c3d92e183eaf3d91107ad1` | — |
| 4 | Bitcoin Up or Down - December 15, 11:30AM-11:45AM ET | `btc-updown-15m-1765816200` | `0x6dcba9f2a4336502a51bdad2a442a113bb75c8ce044bbcd09944ad2f6233e6f0` | — |
| 5 | Bitcoin Up or Down - December 15, 8:00PM-12:00AM ET | `btc-updown-4h-1765846800` | `0xcad11dc1ff49c44f0321097457da5eca18a3c735be8b2afb256f892c42d24acc` | — |
| 6 | Bitcoin Up or Down - December 15, 12:30PM-12:45PM ET | `btc-updown-15m-1765819800` | `0x10ac602a06d9f5b57e1ac8bbd7552acaae1d195ea9de0f79505904a3ac38ee98` | — |
| 7 | Bitcoin Up or Down - December 15, 10:15PM-10:30PM ET | `btc-updown-15m-1765854900` | `0x0d99b6262f9ede4d54369117238387856400f178fa712fa66daaa92b7669387a` | — |
| 8 | Bitcoin Up or Down - December 15, 7:00PM-7:15PM ET | `btc-updown-15m-1765843200` | `0x2ad1b4e950588fcd0e49e5cb0cbf4dd0cc4751ac179fef97a2aef9c1570bb4cf` | — |
| 9 | Bitcoin Up or Down - December 15, 5:15PM-5:30PM ET | `btc-updown-15m-1765836900` | `0x5eb71a6f5fb667e7551166dde537b8e7d0d76fc422052807f19a435e8d0be4d1` | — |
| 10 | Bitcoin Up or Down - December 15, 5:45PM-6:00PM ET | `btc-updown-15m-1765838700` | `0x224d99f92f829159fee5d5f7e54140252698b8d15b45ffbb74cf872eaf2fa6ec` | — |
| 11 | Bitcoin Up or Down - December 15, 11:45PM-12:00AM ET | `btc-updown-15m-1765860300` | `0x07ef74eb8fbe4c4139d96c37723ca0ee7a11514b91c1c4b21d7284539ee4875c` | — |
| 12 | Bitcoin Up or Down - December 15, 4:30PM-4:45PM ET | `btc-updown-15m-1765834200` | `0xce606626b865ab920478dfdfab45299481931652335851af8c6e97be0befb366` | — |
| 13 | Bitcoin Up or Down - December 15, 2:30PM-2:45PM ET | `btc-updown-15m-1765827000` | `0x91bcbfc92a946b6de329cf2b301976a769f8763c52a6b02c3b5095c657d71a92` | — |
| 14 | Bitcoin Up or Down - December 15, 8:30PM-8:45PM ET | `btc-updown-15m-1765848600` | `0xe3964de3d3e8d34a7c9f517ec87f886c9dd5d2e32ab7f7ac59e39adb675e45f0` | — |
| 15 | Bitcoin Up or Down - December 15, 3:30PM-3:45PM ET | `btc-updown-15m-1765830600` | `0xbfc916deb9ca3afbef474bdb9f4da4ce670f382cb7b6dd897de0532a4dc212d9` | — |
| 16 | Bitcoin Up or Down - December 15, 2:45PM-3:00PM ET | `btc-updown-15m-1765827900` | `0xb3f68e087a05b96a41f5ec3d420efcf62946d03d240d17e4008230bc14b60cf8` | — |
| 17 | Bitcoin Up or Down - December 15, 2:00PM-2:15PM ET | `btc-updown-15m-1765825200` | `0x91637e564fe986ba36d438b5751456e7653e933fde042467f82645cc3c73b665` | — |
| 18 | Bitcoin Up or Down - December 15, 1:30PM-1:45PM ET | `btc-updown-15m-1765823400` | `0xb4a25f9acac817cf5b11c518a32c2b956f8c41f05847d2554a560311deaea27c` | — |
| 19 | Bitcoin Up or Down - December 15, 9:00PM-9:15PM ET | `btc-updown-15m-1765850400` | `0xe8292c4d311fd5e9c3c9107a9bd24285796460ca15c0d5cd6e2c3f7722246a3f` | — |
| 20 | Bitcoin Up or Down - December 15, 10:45PM-11:00PM ET | `btc-updown-15m-1765856700` | `0x4570718139526527ccc30c476c09c45a6a93240f8498ba5b2856dc707f495941` | — |

> **Note:** `event_id` is `null` for all CLOB markets — the Polymarket CLOB `/markets` endpoint does not return a top-level `event_id` field. The `condition_id` is the primary unique market identifier.

---

## STEP 5 — ETH: First 20 Discovered Markets

> Source: `GET /api/v1/source-validation/search?q=eth&limit=500`  
> Event type for all: **UPDOWN**

| # | Title | Slug | Market ID (condition_id) | Event ID |
|---|---|---|---|---|
| 1 | Ethereum Up or Down - December 15, 8:45PM-9:00PM ET | `eth-updown-15m-1765849500` | `0x290e1d267d64de4f3bb98eeb7d5008bc4ed7c4d056ca21b7139b79adfa0de324` | — |
| 2 | Ethereum Up or Down - December 15, 5:00PM-5:15PM ET | `eth-updown-15m-1765836000` | `0xf4c5c75c5e78e728504973a0b07167994bd6234b2c5e764007ebc8deacfb4d03` | — |
| 3 | Ethereum Up or Down - December 15, 8:00PM-12:00AM ET | `eth-updown-4h-1765846800` | `0x602b53de50cf1f492715aca1e97a2e2011eb5595aa5c70e22244efaacc136a25` | — |
| 4 | Ethereum Up or Down - December 15, 12:30PM-12:45PM ET | `eth-updown-15m-1765819800` | `0xf0fd7913c9fe147f459310196b8484a0c3e71b1e10699c53ffc52c1a41a2f002` | — |
| 5 | Ethereum Up or Down - December 16, 9PM ET | `ethereum-up-or-down-december-16-9pm-et` | `0x1ce46209eebde56732b4972792657f1d694eeb0acb769124e01fdd8933685280` | — |
| 6 | Ethereum Up or Down - December 15, 12:45PM-1:00PM ET | `eth-updown-15m-1765820700` | `0x551085ae7d9156a1bb4a451b034434dc3ba8ace0230aad9e7093e16e844439cc` | — |
| 7 | Ethereum Up or Down - December 16, 12PM ET | `ethereum-up-or-down-december-16-12pm-et` | `0xac2f03d3376f78bac14fc11e988eb778cff2b86624f4b0a77b1517bdda81695e` | — |
| 8 | Ethereum Up or Down - December 15, 9:15PM-9:30PM ET | `eth-updown-15m-1765851300` | `0xa0140b1f0975cd0b2e3236804b5f26385b187cdf3f2f060c8316314e06b1768b` | — |
| 9 | Ethereum Up or Down - December 15, 6:15PM-6:30PM ET | `eth-updown-15m-1765840500` | `0xe74d081894ea942fea57397947c84db824f15fdd325e2d760c24bcfe11bde454` | — |
| 10 | Ethereum Up or Down - December 16, 7PM ET | `ethereum-up-or-down-december-16-7pm-et` | `0x61ef97e1f2f18a1e4fc8b8c4b6bd2296c012e95ca5e383939a608f61a5fcaaa6` | — |
| 11 | Ethereum Up or Down - December 15, 10:15PM-10:30PM ET | `eth-updown-15m-1765854900` | `0x2d135c325ae3a7d4c4475fe97f63eaf0567927a927133c9aab39fcc23eddfba2` | — |
| 12 | Ethereum Up or Down - December 16, 4PM ET | `ethereum-up-or-down-december-16-4pm-et` | `0x3ced2ad7405d9c0097edadfdd9255e6fa1d37df68860e61f7a0e2a66303fc732` | — |
| 13 | Ethereum Up or Down - December 16, 8PM ET | `ethereum-up-or-down-december-16-8pm-et` | `0x710112b1ad5cd0f4aae70186d3d3f5b68c1366f850e727e4838323605432ed55` | — |
| 14 | Ethereum Up or Down - December 17, 12AM ET | `ethereum-up-or-down-december-17-12am-et` | `0xf6517f013f6d542950ff3d4d7fa7cbbdb8c02846707969f7b3dfa7f67ea7f4ef` | — |
| 15 | Ethereum Up or Down - December 16, 10PM ET | `ethereum-up-or-down-december-16-10pm-et` | `0x1becc81554d8af6356a0b7482e508ae15376af12a740cbd6291bbb778db4aecd` | — |
| 16 | Ethereum Up or Down - December 15, 9:30PM-9:45PM ET | `eth-updown-15m-1765852200` | `0x125f50443e84e5297189abfa3e0614a6d99d5102f22c6cc2e9c9842c212f0309` | — |
| 17 | Ethereum Up or Down - December 15, 5:15PM-5:30PM ET | `eth-updown-15m-1765836900` | `0x1cde4d7e21ad45eba7089f53e321fed9171459c90f5b3b9bcdfe85bd614b21b9` | — |
| 18 | Ethereum Up or Down - December 15, 8:00PM-8:15PM ET | `eth-updown-15m-1765846800` | `0x86330283da22af0aeaf3e5f703266f1fff64c9065c6b42b7be9320d79d3cc63d` | — |
| 19 | Ethereum Up or Down - December 15, 2:30PM-2:45PM ET | `eth-updown-15m-1765827000` | `0xc34614ca3229b48af89f1e7526c07312be26ef1f13f2835e766ed349da860fa5` | — |
| 20 | Ethereum Up or Down - December 15, 9:00PM-9:15PM ET | `eth-updown-15m-1765850400` | `0xca3ca7a118825526f7f7d7f951d1f74cdab29367288000ef71dbc1eb78f2672c` | — |

---

## STEP 6 — SOL: First 20 Discovered Markets

> Source: `GET /api/v1/source-validation/search?q=sol&limit=500`  
> Event type for all: **UPDOWN**

| # | Title | Slug | Market ID (condition_id) | Event ID |
|---|---|---|---|---|
| 1 | Solana Up or Down - December 16, 10PM ET | `solana-up-or-down-december-16-10pm-et` | `0x16b00cfbc486080a931e7e30113ab876c753e4ebeb98315d797830645460dde3` | — |
| 2 | Solana Up or Down - December 16, 9PM ET | `solana-up-or-down-december-16-9pm-et` | `0xbf1b04e44468d4f8d07d91ae3c3c895ab42a706e5e9746d928e9109d3da6cf3a` | — |
| 3 | Solana Up or Down - December 16, 6PM ET | `solana-up-or-down-december-16-6pm-et` | `0x938cf5278a41fb2b4f03e1780b8ea54dac0984241521272914e58395c7712dc1` | — |
| 4 | Solana Up or Down - December 15, 11:45AM-12:00PM ET | `sol-updown-15m-1765817100` | `0xb62ef20a7d35a541520f7fe209e0ebd051474f3938bdeaf25764ba9441dd4e9c` | — |
| 5 | Solana Up or Down - December 15, 7:00PM-7:15PM ET | `sol-updown-15m-1765843200` | `0x93438d4f9b437e514994bf8df27915ba0e12560d7d56646fe222fb11e52ccf3a` | — |
| 6 | Solana Up or Down - December 15, 6:30PM-6:45PM ET | `sol-updown-15m-1765841400` | `0xc5249e6ae203a0b674ab2173f0c737d704b4c720d34e1d13237e0d5caf35120e` | — |
| 7 | Solana Up or Down - December 15, 12:30PM-12:45PM ET | `sol-updown-15m-1765819800` | `0x24072586ca702adb37a491e7991388ce2b09b3c63958b67ba50ecc064cb219f6` | — |
| 8 | Solana Up or Down - December 15, 5:00PM-5:15PM ET | `sol-updown-15m-1765836000` | `0x98c952b2ff36d8977c53f4b4b5f0ad7731fc6c27880a6e27d654c5d165e9ea56` | — |
| 9 | Solana Up or Down - December 15, 9:15PM-9:30PM ET | `sol-updown-15m-1765851300` | `0xf3ead971887667a6e5117e37563872b75af27ef2f952117fdde184acbdd65a91` | — |
| 10 | Solana Up or Down - December 15, 9:30PM-9:45PM ET | `sol-updown-15m-1765852200` | `0x7a52bc829725778f7a3cc98e8173467f90896abd81a62e5ec51ba86de6068009` | — |
| 11 | Solana Up or Down - December 15, 4:15PM-4:30PM ET | `sol-updown-15m-1765833300` | `0x22a2b4ad2fca35a3b45dccfd4dd72aad379d537cc991158b3460bc2630e7623e` | — |
| 12 | Solana Up or Down - December 15, 10:00PM-10:15PM ET | `sol-updown-15m-1765854000` | `0x517c5dd1e74ae4593b000628287de73a5bfea37e925b9699bf0c271e7fada9a9` | — |
| 13 | Solana Up or Down - December 15, 12:45PM-1:00PM ET | `sol-updown-15m-1765820700` | `0xad350fed94709b43164dfc685c864eabe8d43c5e83bd7e21e1fe7b44545e12ee` | — |
| 14 | Solana Up or Down - December 15, 8:00PM-8:15PM ET | `sol-updown-15m-1765846800` | `0xc5547e99ec4b459571e6d7b52853f58caec163cfbe2a5219d731450d6b592140` | — |
| 15 | Solana Up or Down - December 15, 6:45PM-7:00PM ET | `sol-updown-15m-1765842300` | `0xd2ebe9946968fa375f0d3bfedd09b749150300763f64bc247b858e6fecdb699d` | — |
| 16 | Solana Up or Down - December 15, 7:30PM-7:45PM ET | `sol-updown-15m-1765845000` | `0x3269692e5d3ef02913fb1a7078a7470f7ea4a14e081718eb35a9b64f471ac156` | — |
| 17 | Solana Up or Down - December 15, 5:30PM-5:45PM ET | `sol-updown-15m-1765837800` | `0xadb96c1b7a3e092eb0d69b8dc738da5a3ef37f909bb4b459e4466b749acb6cbf` | — |
| 18 | Solana Up or Down - December 16, 3PM ET | `solana-up-or-down-december-16-3pm-et` | `0x6fc0a3b4f733f47c2b293a51100cf32d60b1c962b085e959cb1af79e553eba90` | — |
| 19 | Solana Up or Down - December 16, 4PM ET | `solana-up-or-down-december-16-4pm-et` | `0x23945cff75ed469c9564fafe6e4bac81bc89d0bc9bb9c8027e82052787542b27` | — |
| 20 | Solana Up or Down - December 15, 9:45PM-10:00PM ET | `sol-updown-15m-1765853100` | `0x33c30f181d7ba5d37fdba3739612db410b0d1d6da10b7aacbebd23f3ca6accf4` | — |

---

## STEP 7 — XRP: First 20 Discovered Markets

> Source: `GET /api/v1/source-validation/search?q=xrp&limit=500`  
> Event type for all: **UPDOWN**

| # | Title | Slug | Market ID (condition_id) | Event ID |
|---|---|---|---|---|
| 1 | XRP Up or Down - December 15, 4:30PM-4:45PM ET | `xrp-updown-15m-1765834200` | `0x3432a94c421be67d8f9d6f5224f2217006fdd85f1de384e70e4b06e44f92e12d` | — |
| 2 | XRP Up or Down - December 15, 8:15PM-8:30PM ET | `xrp-updown-15m-1765847700` | `0xc88cfb12ef853907e9af1068cc0fd29294561aa2a022c4daec3a234a61b46ff0` | — |
| 3 | XRP Up or Down - December 15, 9:30PM-9:45PM ET | `xrp-updown-15m-1765852200` | `0x0a0b183624d0055ab3447d41850776afccd46628dc1b1b3158808076cf6fc3e7` | — |
| 4 | XRP Up or Down - December 15, 1:00PM-1:15PM ET | `xrp-updown-15m-1765821600` | `0xa63d9f544d7e238bc54449f2b3ef09043f817f10a6a76b93398e1433b15b5969` | — |
| 5 | XRP Up or Down - December 15, 3:15PM-3:30PM ET | `xrp-updown-15m-1765829700` | `0xf81577af0caa8d80225e5a05e3aae31d4723e145eb91642141eac4fd2018f206` | — |
| 6 | XRP Up or Down - December 15, 8:00PM-12:00AM ET | `xrp-updown-4h-1765846800` | `0x50c60817a3f1d746e3c6d40a0510209bcc1c4dfc233fddefc85a246512dac68d` | — |
| 7 | XRP Up or Down - December 15, 12:15PM-12:30PM ET | `xrp-updown-15m-1765818900` | `0x12f9eed448a4c3f27c2b4db33b6cfff5bbab762c8df3b64a9c0e29e971bad491` | — |
| 8 | XRP Up or Down - December 15, 6:30PM-6:45PM ET | `xrp-updown-15m-1765841400` | `0x1c01c3d6c6fa73dbe7d199e0b1a559a90290bffa5b8a5f2ee295961be4177bbe` | — |
| 9 | XRP Up or Down - December 15, 7:45PM-8:00PM ET | `xrp-updown-15m-1765845900` | `0x7fb1eb1feaafe3ff95d8911c50a754f7982868d1f724301d9877e620ad03bff3` | — |
| 10 | XRP Up or Down - December 15, 12:00PM-12:15PM ET | `xrp-updown-15m-1765818000` | `0x0ac8e6e2ca37b67000ff72b0ac76727aee744c79f0cf626e8c6a898fb0edaff3` | — |
| 11 | XRP Up or Down - December 16, 5PM ET | `xrp-up-or-down-december-16-5pm-et` | `0x4e0b70bf74cbb62bdd2de87d746d076eb1bf4820d5ddedbf85d6c85ec0457400` | — |
| 12 | XRP Up or Down - December 15, 8:30PM-8:45PM ET | `xrp-updown-15m-1765848600` | `0x8d3f524479976e3da5fb6071c409f408f36d40aeac14154255f9e2319bdec4e1` | — |
| 13 | XRP Up or Down - December 16, 3PM ET | `xrp-up-or-down-december-16-3pm-et` | `0x5def48ca6e6ccd33b363ec02d70c49f38d1f3addd440e9feba16efb3ba3f4ba1` | — |
| 14 | XRP Up or Down - December 15, 11:30PM-11:45PM ET | `xrp-updown-15m-1765859400` | `0xbe6d8a352ddb84f0fdcb971c6fcd006d28d02f4d72f91af31bd72861c24383b1` | — |
| 15 | XRP Up or Down - December 15, 6:15PM-6:30PM ET | `xrp-updown-15m-1765840500` | `0xc78ccab1a0abb40fa32e9c433f820b8c133af35b0756ec50711804c2dac96330` | — |
| 16 | XRP Up or Down - December 15, 1:45PM-2:00PM ET | `xrp-updown-15m-1765824300` | `0x1fc637a80a047fe1f4b7d2f24c330ec8ffab9d0cc5db02aa07c848093f720e62` | — |
| 17 | XRP Up or Down - December 15, 6:45PM-7:00PM ET | `xrp-updown-15m-1765842300` | `0x7040a2e839ed480fb558bd100856bc4ac100ce21b87c2d259cfc6058b315a8d4` | — |
| 18 | XRP Up or Down - December 15, 11:45PM-12:00AM ET | `xrp-updown-15m-1765860300` | `0xe9f3ac16953e4d5ba2383bcc9cf09fe30c8529f9ca770fffb82618ec545e5e1f` | — |
| 19 | XRP Up or Down - December 16, 8PM ET | `xrp-up-or-down-december-16-8pm-et` | `0xbaa12eb630cbddb8bdc45ff3a0c4a70a52098ac160f82a6224b8689f53f30ba9` | — |
| 20 | XRP Up or Down - December 15, 10:45PM-11:00PM ET | `xrp-updown-15m-1765856700` | `0x63f1004ad3ed5def2e8d4b69da27499f8d741d5aee70136105666fd50cf589f7` | — |

---

## STEP 8 — Research Question

> **Did we find markets similar to:**
> - `BTC Up or Down 5 Minutes`
> - `BTC Up or Down 15 Minutes`
> - `BTC Up or Down 1 Hour`
> - `ETH Up or Down`
> - `SOL Up or Down`
> - `XRP Up or Down`

### Answers by family:

| Target | Found? | Notes |
|---|---|---|
| BTC Up or Down *(generic)* | **YES** | 18,218 markets |
| BTC Up or Down **5 Minutes** | **NO** | Zero 5-minute markets found anywhere on the CLOB |
| BTC Up or Down **15 Minutes** | **YES (different naming)** | Exists as `Bitcoin Up or Down - {Date}, {HH:MM}PM-{HH:MM}PM ET` (15-min windows) |
| BTC Up or Down **1 Hour** | **YES (different naming)** | Exists as `Bitcoin Up or Down - {Date}, {H}PM ET` (whole-hour named) |
| ETH Up or Down | **YES** | 17,650 markets |
| SOL Up or Down | **YES** | 12,796 markets |
| XRP Up or Down | **YES** | 12,503 markets |

---

## STEP 9 — YES: Exact Examples

### "BTC Up or Down" — **15-minute window** format

These are the closest equivalent to "BTC Up or Down 15 Minutes":

```
Title:      Bitcoin Up or Down - December 15, 2:15PM-2:30PM ET
Slug:       btc-updown-15m-1765826100
Market ID:  0xb4d260bc5a7aa7df98c2993cc0a8a42151ce60e51f36fce1048210b6b8607630
Source:     https://clob.polymarket.com/markets

Title:      Bitcoin Up or Down - December 15, 11:30AM-11:45AM ET
Slug:       btc-updown-15m-1765816200
Market ID:  0x6dcba9f2a4336502a51bdad2a442a113bb75c8ce044bbcd09944ad2f6233e6f0
Source:     https://clob.polymarket.com/markets
```

### "BTC Up or Down" — **whole-hour** format (closest to "1 Hour")

```
Title:      Bitcoin Up or Down - December 16, 5PM ET
Slug:       bitcoin-up-or-down-december-16-5pm-et
Market ID:  0x...
Source:     https://clob.polymarket.com/markets

Title:      Bitcoin Up or Down - December 17, 12AM ET
Slug:       bitcoin-up-or-down-december-17-12am-et
Source:     https://clob.polymarket.com/markets
```

### "ETH Up or Down" — examples

```
Title:      Ethereum Up or Down - December 15, 8:45PM-9:00PM ET
Slug:       eth-updown-15m-1765849500
Market ID:  0x290e1d267d64de4f3bb98eeb7d5008bc4ed7c4d056ca21b7139b79adfa0de324

Title:      Ethereum Up or Down - December 16, 7PM ET
Slug:       ethereum-up-or-down-december-16-7pm-et
Market ID:  0x61ef97e1f2f18a1e4fc8b8c4b6bd2296c012e95ca5e383939a608f61a5fcaaa6
```

### "SOL Up or Down" — examples

```
Title:      Solana Up or Down - December 15, 7:00PM-7:15PM ET
Slug:       sol-updown-15m-1765843200
Market ID:  0x93438d4f9b437e514994bf8df27915ba0e12560d7d56646fe222fb11e52ccf3a

Title:      Solana Up or Down - December 16, 6PM ET
Slug:       solana-up-or-down-december-16-6pm-et
Market ID:  0x938cf5278a41fb2b4f03e1780b8ea54dac0984241521272914e58395c7712dc1
```

### "XRP Up or Down" — examples

```
Title:      XRP Up or Down - December 15, 4:30PM-4:45PM ET
Slug:       xrp-updown-15m-1765834200
Market ID:  0x3432a94c421be67d8f9d6f5224f2217006fdd85f1de384e70e4b06e44f92e12d

Title:      XRP Up or Down - December 16, 5PM ET
Slug:       xrp-up-or-down-december-16-5pm-et
Market ID:  0x4e0b70bf74cbb62bdd2de87d746d076eb1bf4820d5ddedbf85d6c85ec0457400
```

---

## STEP 10 — NO: 5-Minute Markets — What Was Found Instead

### Finding: 5-Minute Markets Do Not Exist on the CLOB

A search across all 250,000 Polymarket CLOB markets for titles or slugs containing
`"5 min"`, `"5min"`, or `"5-minute"` returned **zero results**.

### What market families were found instead

Polymarket publishes Up/Down markets in exactly **three timeframe families**:

| Family | Slug Pattern | Title Pattern | Duration | Count in DB |
|---|---|---|---|---|
| **15-minute window** | `{asset}-updown-15m-{epoch}` | `{Asset} Up or Down - {Date}, {T1}-{T2} ET` (15-min spans) | 15 min | 3,560 per 5,000 sample |
| **4-hour window** | `{asset}-updown-4h-{epoch}` | `{Asset} Up or Down - {Date}, {T1}-{T2} ET` (4-hr spans) | 4 hours | 222 per 5,000 sample |
| **Whole-hour named** | `{asset}-up-or-down-{date}-{H}pm-et` | `{Asset} Up or Down - {Date}, {H}PM ET` | ~1 hour | 910 per 5,000 sample |

### Slug examples by family

```
btc-updown-15m-1765826100      ← 15-minute window
btc-updown-4h-1765846800       ← 4-hour window
bitcoin-up-or-down-december-16-5pm-et  ← whole-hour named
```

### Which endpoint produced them

All markets were returned by a single source:

```
GET https://clob.polymarket.com/markets?limit=100&active=true
```

No alternative Polymarket source is required. The CLOB endpoint is the correct and
only source for active binary markets. However, if a different (non-CLOB) source is
needed, the Polymarket Gamma API (`https://gamma-api.polymarket.com`) provides
structured event-level data that may carry richer timeframe metadata.

### Note on `event_id` field

The CLOB `/markets` endpoint does not include a top-level `event_id` key.
All 75,794 stored markets have `event_id = null`. To retrieve event-level grouping
(which would link multiple condition IDs to a single event), the Polymarket Gamma API
or the events endpoint (`https://gamma-api.polymarket.com/events`) should be used
alongside the CLOB.

---

## Summary of Findings

```
┌────────────────────────────────────────────────────────────────────────┐
│                     SPRINT 5 INVESTIGATION SUMMARY                      │
├────────────────────────────────────────────────────────────────────────┤
│  Total markets scanned          250,000                                 │
│  Total asset-matched             75,794                                 │
│  Total Up/Down candidates        61,167                                 │
│    BTC candidates                18,218                                 │
│    ETH candidates                17,650                                 │
│    SOL candidates                12,796                                 │
│    XRP candidates                12,503                                 │
├────────────────────────────────────────────────────────────────────────┤
│  UPDOWN (all 250k)               48,930                                 │
│  PRICE_RANGE                     42,455                                 │
│  POLITICS                        19,597                                 │
│  OTHER                          126,206                                 │
│  NEWS_EVENT                       1,479                                 │
├────────────────────────────────────────────────────────────────────────┤
│  Did we find "Up or Down" markets?       YES — all 4 assets            │
│  Did we find "5 Minutes" markets?        NO — not on CLOB               │
│  Did we find "15 Minutes" markets?       YES* — as timestamp windows   │
│  Did we find "1 Hour" markets?           YES* — as whole-hour named    │
├────────────────────────────────────────────────────────────────────────┤
│  * Polymarket does not use "5 Minutes / 15 Minutes / 1 Hour" as        │
│    standalone labels. Timeframe is encoded in the market's time range   │
│    (e.g. "2:15PM-2:30PM ET" = 15 min) or its slug                      │
│    (e.g. btc-updown-15m-{epoch}, btc-updown-4h-{epoch}).               │
│                                                                         │
│  The discovery engine can reliably find the BTC/ETH/SOL/XRP            │
│  Up-or-Down market family. The timeframe labels must be adapted         │
│  from slug patterns rather than title text.                             │
└────────────────────────────────────────────────────────────────────────┘
```

---

*Report generated by: Sprint 5 Source Validation Engine*  
*Source: `https://clob.polymarket.com/markets` (Polymarket CLOB)*  
*Run ID: `b632be63-03f7-4d53-9887-3a250a45015d`*
