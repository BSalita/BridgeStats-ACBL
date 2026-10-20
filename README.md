# BridgeStats-ACBL

This project contains source code for https://7nt.info, a website which displays ACBL bridge statistics. GitHub repository: https://github.com/BSalita/BridgeStats-ACBL 

The website server requires at least 64GB of memory.

Website is written in Streamlit. Dependencies are in requirements.txt.

To install:

`pip install -r requirements.txt`

To run:

`streamlit run Home.py`

You can host the website locally and use cloudflare tunnels to forward streamlit port 8501 for public access.

Data is only available, from this project's author, for those who sign ACBL's NDA or register for ACBL's API. The data is primarily oriented for consumption by a machine learning model as opposed to human readability. The data is created by both scraping ACBL's website and using their APIs. The data creation process is extremely resource intensive and requires at least 128GB multi-core systems. Source code for building the data is not yet available.

## Design notes

### Contract rarity and n-off contracts (designed, not implemented)

Decision (October 2026): documented only, in ACBL and FFBridge BridgeStats alike. The postmortem
"unique bids" favorites are unchanged.

- Key: per board (`session_id`, `HandRecordBoard`), a contract is
  `BidLvl || BidSuit || Dbl || NS/EW`. Rows without a contract (`BidLvl IS NULL`) are skipped, and
  boards need at least 4 tables.
- `Tables` is `COUNT(*) OVER (PARTITION BY session_id, HandRecordBoard)` and `Same_Contract` adds
  the contract key to the partition.
- n-off: `Same_Contract` itself. 1-off means only that table played the contract, 2-off means
  two tables did, and so on. A frequency favorite counts a player's boards by n-off.
- Rarity: `-log2(Same_Contract / Tables)` bits, and excess bits relative to the board average. A
  leaderboard averages them over a player's declared or dummy boards.
- Attribution: declarer and dummy names come from the `Player_Name_*` seat columns through
  `Declarer_Direction`, not from `Declarer_Name`.
- The candidate SQL starts with a `sessions` CTE filtered by the date, club, player, and pair
  macros. It then scans every row of those sessions, because the field is needed to count
  contracts. So `/favorites/{id}` would have to stop pre-filtering to the player's own rows.
- Use `Tricks - BidLvl - 6` for over/under; see the `result` / `Result` issue below.

Measured cost per query at 8 DuckDB threads, against roughly 4 s and 1.5 GB for an existing
declarer favorite:

| Dataset | Last 12 months | Full history |
|---|---|---|
| ACBL tournament | 7.6–8.7 s, 2.8 GB | 21–49 s, 4.9–9.7 GB |
| ACBL club | 14–36 s | 51–222 s, 12–14 GB |
| FFBridge | 0.9–2.3 s, ≤ 0.7 GB | 3.2–8.5 s, about 2 GB |

The cost is paid per request; nothing is precomputed. Precomputing in the pipeline would make
queries cheap, but it would need a rebuild of the 76 GB club file.

### DuckDB thread cap

Every query-serving DuckDB connection uses `threads = 8` (`DUCKDB_THREADS` in
`bridge_api_common.py`, and likewise in Elo, the four postmortem services, and the chatbot).
DuckDB's default is every core (128 on the server). Window-heavy favorites ran 2–14× slower at 128
threads than at 8, and simple aggregates were no faster. 8 and 16 threads measured about the same.

### Heavy favorites

`Pair_Head_To_Head` and `Identical_Boards` self-join the field. With no player or pair filter
over 12 months of FFBridge data, `Pair_Head_To_Head` took 339 s and 50 GB and returned 28M rows,
and `Identical_Boards` took 39 s and 10.8 GB. ACBL club data is several times larger. The API
materializes the whole result before truncating it to the row limit, so run these with a
player or pair filter.

### Data issues fixed in the pipelines (October 2026)

These take effect once the parquets are rebuilt.

- ACBL club doubles: step 1 removed only the first space from contracts, so `5 C x` parsed as
  undoubled. About 2.8M doubled club contracts were stored without the X, and `Result`/`Tricks`
  were then inferred from the score against the wrong contract. Tournament contracts have no
  spaces and were not affected.
- ACBL club `result` / `Result`: the raw ACBL string (`=`, `+1`, `-2`) sat next to the integer
  `Result`. DuckDB is case-insensitive, so SQL `Result` resolved to the string. Step 1 now turns
  ACBL's `result` and `tricks_taken` into `Result` and `Tricks` and drops the raw columns.
- ACBL player id `0` (SQLite casts a missing ACBL number to 0) is shared by every player without
  a number. It is not yet changed; Elo keys ratings on player id. Exclude `0` when ranking players.

## Related Projects
- https://github.com/BSalita/Bridge_Game_Postmortem_Chatbot
- https://github.com/BSalita/BBO-Downloader
- https://github.com/BSalita/BBO-Lin-Parser
- https://github.com/dds-bridge/dds
- https://github.com/anntzer/redeal
- https://github.com/dominicprice/endplay
- https://github.com/lorserker/ben
- https://github.com/liu1000/bidly
- https://github.com/jdh8/bml
- https://github.com/gpaulissen/bml
- https://github.com/gpaulissen/bridge-systems
- https://github.com/Kungsgeten/bml
- https://github.com/gpaulissen/bridge-systems
- https://github.com/kdblocher/bridge
- https://github.com/ContractBridge/pbn-files
- https://github.com/jfklorenz/Bridge-Package
- https://github.com/jfklorenz/Card-Deck-Package
- https://github.com/jfklorenz/Bridge-Scoring-Package
- https://github.com/kdblocher/bridge
- https://github.com/ContractBridge/pbnj
- https://github.com/oriyanh/Bridge-AI
- https://github.com/zek/Bridge-Game
- https://github.com/andrewimcclement/practice_bidding
- https://github.com/jasujm/bridge
- https://sourceforge.net/projects/bidbase/files/CardShark%20BidBase%20Bidding%20Practice%20Program/

## Related Documents
- https://www.tistis.nl/pbn/
- https://github.com/jfklorenz/Bridge-Documents
- http://home.claranet.nl/users/veugent/pbn/pbn_v20.txt
- https://www.jeff-goldsmith.com/bridge/glossary.html
- https://en.wikipedia.org/wiki/Glossary_of_contract_bridge_terms
- https://markdown.land/markdown-cheat-sheet
- https://www.color-hex.com/
