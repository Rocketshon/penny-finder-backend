# Penny Hunter — Digital Coupon Sources

Tiered roadmap for surfacing digital / printable coupons in-app.

---

## Tier 1 — DG-specific (LIVE)

**File**: `scrapers/dg_coupons.py`
**Source**: `https://www.dollargeneral.com/deals/coupons` (Playwright-rendered)
**Output**: DealItems with `store_id='dg'`, `source='dg-coupon'`, `sale_story` includes the discount + "DG digital coupon — clip in app".

**How users use them**: tap the deal in our app → they're directed to clip the coupon themselves in the official DG app/website. We never claim or modify on their behalf (no DG account needed for us).

**Risks**:
- DG's React markup changes occasionally; the heuristic CSS selectors may break. Scraper degrades gracefully (returns empty + flags Source.ok=false in the briefing's `sources` panel).
- Playwright is slow (+30s to daily run) and adds memory pressure. Already amortized across the existing playwright_tfg scraper; one more browser-rendered source is fine.

---

## Tier 2 — Manufacturer coupons aggregator (LIVE)

**File**: `scrapers/coupons_com.py`
**Source**: `https://www.coupons.com/coupons/` (Playwright-rendered)
**Output**: DealItems with `store_id='online'` (cross-retailer), `source='coupons-com'`, `sale_story` includes "manufacturer coupon — print or load to retailer card".

**Coverage**: Procter & Gamble, Unilever, Kimberly-Clark, General Mills, etc. Most coupons work at any major retailer accepting paper coupons. Surfacing them lets users stack with penny-day finds and weekly-ad sales.

**Why aggregator vs per-retailer**: Coupons.com's listings include manufacturer coupons that DON'T map to a single store. Tagging them as `store_id='online'` keeps them out of per-store deal lists but makes them browsable via the Categories tab. Future enhancement: a dedicated "🎟️ Coupons" tab.

---

## Tier 3 — Direct retailer coupon programs (RESEARCH ONLY)

Each major retailer has a digital-coupon program. Most require either a partner API or post-login scraping. Documented here as future work.

### Walmart
- **Public coupons**: walmart.com/cp/coupons (no login)
- **API**: Walmart Affiliate API (https://affiliates.walmart.com) has a Coupon endpoint, but requires partnership approval (~2-week process). API returns JSON; once approved this becomes the cleanest source.
- **Workaround**: Playwright scrape walmart.com/cp/coupons. Same pattern as DG — 30s render, 50-200 coupons typical.

### Target — Circle
- **Program**: Target Circle (formerly Cartwheel)
- **Public access**: NO. Coupons require a Target.com login + tied to your Target Circle membership.
- **Possible path**: Affiliate API via Impact (Target uses Impact as affiliate network). Impact has limited coupon visibility.
- **Realistic answer**: Target Circle offers can ONLY be obtained by signing into their app/site. Not scrapeable.

### CVS — ExtraCare
- **Program**: ExtraCare Bucks + manufacturer coupons
- **Public access**: cvs.com/extracare/manage/getextras shows generic offers; ExtraBucks attached to ExtraCare card after login
- **Scrapeable surface**: weekly ad we already scrape (cvs.py + flipp.py)
- **Realistic answer**: surface manufacturer coupons via Coupons.com (already done in Tier 2). ExtraBucks need user login — out of scope.

### Walgreens — myWalgreens
- Same story as CVS. Public weekly ads we already scrape; loyalty offers gated behind login.

### Kroger — Kroger Plus
- **Public coupons**: kroger.com/cl/coupons-deals/coupons (paginated)
- **API**: Kroger Public API (api-ce.kroger.com) — we already use it for kroger.py briefing data. Has a `/products` endpoint with promo info but no dedicated coupons endpoint in the public tier.
- **Possible path**: Playwright scrape kroger.com/cl/coupons-deals/coupons. Same pattern as DG.

### Publix — Publix Digital Coupons
- **Public**: publix.com/savings/digital-coupons (Playwright scrapeable)
- **No partner API**

### Meijer — mPerks
- **Program**: mPerks (login required for personalized offers)
- **Public manufacturer ads**: scrapeable via Flipp (already wired)

### Dollar Tree, Family Dollar, Five Below
- Limited coupon programs; what they have is on their main weekly ad pages (already wired via Flipp + their own scrapers).

### TJX (TJ Maxx, Marshalls, HomeGoods, Sierra)
- No traditional coupon program. Discounts come via clearance markdowns + the TJX Rewards credit card.

---

## Recommended order to add Tier 3 scrapers

1. **Kroger coupons** (Playwright, ~1 hr) — high user value, big chain
2. **Publix coupons** (Playwright, ~1 hr) — big in southeast US
3. **Walmart public coupons** (Playwright, ~1 hr) — biggest chain by volume
4. **Walmart Affiliate API** (~1 week, partnership approval) — when we have launch traction

NOT pursuing:
- Target Circle (login-walled)
- CVS / Walgreens loyalty offers (login-walled)
- Meijer mPerks (login-walled)

For login-walled programs, the most we can do is link out: "Open the Target app to claim Circle offers." That's not coupons-in-our-app, it's a re-direct.

---

## Display in app (next step)

Once the Tier 1+2 scrapers run successfully, every relevant DealItem will have a `sale_story` containing "coupon". The app already renders `sale_story` in deal lists. Add a 🎟️ chip when `sale_story` matches /coupon/i so users see at a glance which deals stack with a coupon.

`PennyFinder/src/screens/CategoryDealsScreen.tsx` line ~115 (or wherever
sale_story renders) — wrap with:

```tsx
{it.sale_story && /coupon/i.test(it.sale_story) && (
  <View style={styles.couponChip}>
    <Text style={styles.couponChipText}>🎟️ COUPON</Text>
  </View>
)}
```
