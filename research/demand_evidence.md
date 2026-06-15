# Demand Evidence & Willingness to Pay

> Maps to **Rubric Component 2 (25%)**. Documents the *process* from a vague idea to a
> defensible demand claim. ⚠️ **Figures marked `[verify]` must be re-checked and cited
> with a real source/date before you submit** — do not ship approximate numbers as facts.

## 1. The hypothesis

Serious recreational NBA bettors will pay a monthly subscription for a tool that
(a) finds the best price across sportsbooks, (b) flags lines the market may have
mispriced, and (c) tracks their CLV and sizes bets correctly — *without* the
scammy "guaranteed picks" framing.

## 2. Is the market real? (public-data analysis)

- **Legalisation tailwind:** the US Supreme Court struck down PASPA in **May 2018**;
  legal sports betting has since expanded to **~38–39 states + DC** `[verify]`. This created
  a large, growing, English-speaking addressable market essentially from scratch.
- **Market size:** US commercial sports-betting revenue was on the order of **~$11B in 2023**
  per the American Gaming Association `[verify exact figure + year]`. Even a tiny analytics
  attach-rate is a meaningful TAM.
- **Active communities (proxy for engaged bettors):**
  - r/sportsbook ≈ **600k+** members `[verify current count]`; daily line-shopping and
    bad-beat threads.
  - r/dfsports, Discord tout groups, Twitter/X "betting model" accounts.
- **Search intent:** Google Trends for `+EV betting`, `line shopping`, `NBA betting model`,
  `closing line value` — capture screenshots and note the trend direction `[do this]`.
- **App-store reviews of incumbents:** mine OddsJam / Action Network reviews for recurring
  praise ("found me +EV") and complaints ("too expensive", "cluttered") → unmet needs `[do this]`.

## 3. Will they pay? (competitor pricing as a WTP anchor)

Existing paid tools prove the willingness to pay exists. Approximate tiers `[verify all]`:

| Product | What it does | Approx. price `[verify]` |
|---|---|---|
| OddsJam | +EV / arbitrage / line shopping | ~$75–150 / mo |
| Unabated | sharp lines, no-vig, line shopping | ~$50+ / mo |
| Action Network (PRO) | odds, tracking, picks | ~$8–13 / mo |
| Outlier.bet | player props / +EV | freemium + sub |

**Read:** the market spans a cheap tracking tier (~$10) to a premium +EV tier (~$75–150).
CourtEdge's wedge is a **focused, transparent, mid-price (~$15–25/mo) +EV + CLV tool** that
undercuts the premium incumbents while doing the few things bettors value most.

## 4. Primary research (survey template — run this, then summarise)

Post in r/sportsbook (respect subreddit rules) or DM 5–15 bettors you know. Questions:

1. How many sportsbooks do you have accounts with? Do you line-shop every bet?
2. Do you currently track your bets? Do you track **CLV** specifically? (Y/N)
3. How do you decide bet size today? (flat / gut / Kelly / other)
4. Have you paid for a betting tool? Which, and how much/month?
5. Would you pay **$X/mo** for auto line-shop + edge flags + CLV tracking? (test X = 10, 20, 30)
6. What's the one thing missing from your current workflow?

Record raw responses in `research/survey/` and summarise: % who line-shop, % who track CLV
(expected to be low → the gap CourtEdge fills), and the price point with the best yes-rate.

## 5. Non-monetary value (time saved)

Manually checking 4 books × ~6 games/night ≈ several minutes/night of comparison; CourtEdge
collapses that to one screen. Quantify minutes saved × nights/season as a value estimate to
complement the monetary WTP.

## 6. Conclusion (to defend in the report)

A large, newly-legal, engaged market already pays $10–150/mo for adjacent tools, yet most
bettors don't track CLV and line-shop inconsistently. That gap — plus a transparent,
no-hype, mid-price positioning — is a defensible wedge. The honest risk (addressed in
`spec.md` §3) is a weak data moat and the efficiency of the market itself.
