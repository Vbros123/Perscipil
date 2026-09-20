# External source registry

Machine-readable complete fields: `data_sources.json`. Implementation is not proof of current reachability or licensing.

|Source|Purpose|Role/status|Freshness days|Rate limit|Reference|
|---|---|---|---:|---|---|
|SEC EDGAR|Financial filings/XBRL|scoring; implemented|400|10 requests/second published maximum; aggregate all workers|[Official reference](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)|
|Wikipedia/Wikidata|Entity identity and age proxies|supporting; implemented|365|UNKNOWN|[Official reference](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use)|
|GLEIF|Legal entity identity|context-only; implemented|365|UNKNOWN|[Official reference](https://www.gleif.org/en/lei-data/gleif-api)|
|Census|Industry statistics|context-only; implemented|365|UNKNOWN|[Official reference](https://www.census.gov/data/developers.html)|
|USASpending|Award evidence|scoring; implemented|365|UNKNOWN|[Official reference](https://api.usaspending.gov/docs/)|
|DuckDuckGo|Public news/context|supporting; implemented|14|UNKNOWN|[Official reference](https://duckduckgo.com/terms)|
|Hacker News / Algolia|Mentions and sentiment proxy|supporting; implemented|14|UNKNOWN|[Official reference](https://hn.algolia.com/api)|
|Indeed|Hiring velocity|unavailable weighted definition; unavailable|14|UNKNOWN|[Official reference](https://www.indeed.com/legal)|
|Creditsafe|Credit and payment evidence|licensed scoring; architected|120|CONTRACT|[Official reference](https://doc.creditsafe.com/connect-apis-catalog/product-catalog/creditrisk)|
|Middesk|Standing/legal evidence|licensed scoring; architected|120|CONTRACT|[Official reference](https://docs.middesk.com/home)|
|Codat|Cash flow|licensed scoring; planned|45|CONTRACT|[Official reference](https://docs.codat.io/)|

SEC fair-access and Wikimedia terms were consulted on 2026-09-20. Other links are review entrypoints, not a claim that their full terms were verified. All retention and redistribution rights remain UNKNOWN pending review. Freshness is signal-specific: Middesk standing is 180 days, litigation 120; the table shows the stricter age. No source is permitted unlimited batch queries.
