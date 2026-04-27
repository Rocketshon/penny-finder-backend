# Penny Hunter — App Store Submission Kit

Everything Apple + Google ask for during submission. Copy/paste-ready.

---

## App Identity

| Field | Value | Notes |
|---|---|---|
| App Name (visible) | **Penny Hunter** | 30-char max, this fits |
| Subtitle (iOS) | **Clearance & reseller deals** | 30-char max (29 used) |
| Bundle ID (iOS) | `com.pennyfinder.app` | Already in app.json |
| Package (Android) | `com.pennyfinder.app` | Already in app.json |
| Primary Category | Shopping | |
| Secondary Category | Lifestyle | |
| Age Rating | 4+ | No objectionable content |
| Content Rating (Google) | Everyone | |
| Default Language | English (US) | |

---

## Subtitle alternatives (pick one for iOS subtitle)

All under 30 chars. Pick whichever resonates.

- `Clearance & reseller deals` (29 chars) ← my pick
- `Markdown intel for hunters` (27 chars)
- `Penny day. Every store.` (24 chars)
- `Find. Hunt. Flip.` (18 chars) — matches our tagline
- `Clearance app for shoppers` (27 chars)

---

## Promotional Text (iOS, 170 chars max — updateable without app review)

```
AI-powered clearance app. 43 retailers tracked. Scan UPCs against penny lists. Best time to visit each store. Receipt OCR with cross-store savings comparison.
```
(159 chars)

---

## Description (iOS 4000 chars / Google 4000 chars)

```
Penny Hunter is the clearance and deal-aggregator app built for serious shoppers — penny hunters, retail-arbitrage flippers, couponers, and anyone who refuses to pay full price.

WHAT IT DOES

• Tracks 43+ major US retailers — Dollar General, Walmart, Target, CVS, Walgreens, Kroger, Meijer, Home Depot, Lowe's, Five Below, TJ Maxx, Hobby Lobby, and more
• AI-categorizes every deal into 12 buckets — tools, beauty, food, pet, tech, apparel — so you can browse "what's on sale in beauty" across every store at once
• Scan-to-check UPC — point your camera at a price tag, instant haptic feedback for a 1-cent match
• Best time to visit each store — live foot-traffic forecasts tell you when to walk in for the freshest markdown shelves
• Receipt scanner with Claude Vision OCR — snap a receipt, see what you could've saved by going elsewhere
• Pair Sync — share watchlist + finds + live store status across two devices in real time, perfect for hunting partners
• Penny-day calendar — Tuesday at Dollar General, Sunday at remodel stores, plus chains nobody else tracks
• AI resale estimates (Pro Mode) — Claude-powered eBay sold-range estimate per UPC, answers "worth flipping?" before you reach the register

BUILT FOR TWO AUDIENCES

Hunters & resellers get penny-day timing, eBay comp lookups, profit ledger with CSV export, hunt-route optimizer, and the DG remodel pipeline tracker.

Casual shoppers get clean discovery — pick a store, pick a category, see what's on sale near you. Watchlist push when something you want hits a flyer.

Toggle "Pro Mode" in Profile to switch between the two experiences.

HOW WE STAY FREE

When you tap "Shop" on a deal and buy from the retailer, we may earn a small affiliate commission via Amazon Associates or Skimlinks. That's it — no subscriptions, no display ads, no data sold to advertisers.

Your watchlist, finds, and receipts stay on your device. The only data that leaves is what YOU choose to share — anonymous UPC confirmations to power "X hunters confirmed" social-proof badges (toggle off any time), or pair-sync data to a single linked device you authorize.

Penny Hunter is not affiliated with, endorsed by, or sponsored by Dollar General, Walmart, Target, Amazon, or any retailer mentioned. All retailer names are property of their owners.

Privacy: pennyhunter.store/privacy
Terms: pennyhunter.store/terms
```

(~2,400 chars — well under both limits)

---

## Keywords (iOS — 100 chars total, comma-separated)

```
penny,clearance,reseller,flipper,arbitrage,coupon,markdown,deal,bargain,DG,thrift,scan,UPC,sale
```
(99 chars — counts include commas)

Picked for App Store SEO + targeted at both audiences.

---

## What's New / Release Notes (first version)

```
🎉 Penny Hunter v1.0 — initial public release.

• 43 retailers tracked across the US
• AI-powered category browser (12 buckets, every store)
• UPC scanner with penny-list match + haptic feedback
• Best time to visit each store (live foot-traffic data)
• Receipt scanner with Claude Vision OCR + cross-store comparison
• Pair Sync — share with one other device in real time
• Pro Mode unlocks resale estimates + eBay comp lookups for flippers

Found a bug or have a feature request? hello@pennyhunter.store
```

---

## App Privacy / Privacy Nutrition Labels (iOS — Apple's exact taxonomy)

This is what you fill out in App Store Connect → App Privacy. Each row maps a data point to Apple's required disclosure.

### Data Linked to You
**None.** We don't collect any data linked to user identity.

### Data Not Linked to You

| Data Type | Used For | Linked? |
|---|---|---|
| Coarse Location (zip / city) | App Functionality (filter deals to your area) | Not Linked |
| Product Interaction | Analytics (PostHog) | Not Linked |
| Crash Data | App Functionality (Sentry) | Not Linked |
| Performance Data | App Functionality | Not Linked |
| Other Diagnostic Data | App Functionality | Not Linked |
| Other User Content (anonymous UPC confirmations, opt-out) | Product Personalization | Not Linked |
| Photos (receipts, on-device, sent to AI for parsing only) | App Functionality | Not Linked |

### Tracking
**None.** We don't track users across other apps or websites.
(Note: outbound affiliate links to retailers DO drop their own cookies once the user lands there. But we don't track within Penny Hunter or sell any data.)

### Data Used to Track You
**None.**

### Apple's "Privacy choices visible in app"
✅ Yes — Profile → Privacy section has two toggles ("Usage Analytics" + "Share Anonymous Finds").

---

## Google Play Data Safety form

Same content as Apple privacy nutrition. Google's form is more granular — match the above across:

- Personal info: **No**
- Financial info: **No**
- Health & fitness: **No**
- Messages: **No**
- Photos & videos: **Yes** — receipt photos, processed on-device + sent to Anthropic for parsing only, not stored on our servers
- Audio files: **No**
- Files & docs: **No**
- Calendar: **No**
- Contacts: **No**
- App activity: **Yes** — page views, in-app actions (analytics; user can opt out)
- Web browsing: **No**
- App info & performance: **Yes** — crash logs, diagnostics
- Device or other IDs: **Yes** — random device-level ID for analytics + a separate random client_id for anonymous finds. Neither is your Apple ID, IDFA, or Google Advertising ID.

Encryption in transit: **Yes** (HTTPS everywhere)
Data deletion: **Yes** — see privacy policy

---

## Support URL + Marketing URL

| Field | URL |
|---|---|
| Marketing URL | https://pennyhunter.store |
| Support URL | https://pennyhunter.store/#contact (we'll add the anchor) or `mailto:hello@pennyhunter.store` |
| Privacy Policy URL | https://pennyhunter.store/privacy |
| Terms of Use URL | https://pennyhunter.store/terms |

---

## Required app icon sizes (iOS)

iOS auto-generates from the 1024×1024 source via Expo's `expo-app-icon` plugin. You only need to provide the 1024×1024 version. EAS Build handles the rest.

Source SVG: `assets/icon-source.svg` (we generate this next)
PNG export: `assets/icon.png` (1024×1024, no alpha, no transparency, no rounded corners — Apple adds those)

Adaptive icon (Android):
- `assets/adaptive-icon.png` — 1024×1024 foreground (paper-cream Penny Hunter wordmark)
- Background color: `#F4EFE4` (paper) — set in app.json

---

## Required screenshots

Apple requires AT LEAST 6.7" iPhone (1290×2796px) screenshots. iPad is optional. You need 3-10 screenshots.

Recommended set (with marketing copy overlays):

1. **Home screen** — "Find. Hunt. Flip. The clearance app for serious shoppers."
2. **Penny screen** — "Penny day countdown. 84 confirmed UPCs."
3. **Categories grid** — "Browse 12 categories across 43 retailers."
4. **Store detail with Best Time card** — "Know when to walk in for the freshest markdowns."
5. **Scanner mid-scan with penny match** — "Scan any UPC. Instant confirmation."
6. **Receipt summary** — "AI-parsed receipt. See what you could've saved elsewhere."
7. **Finds ledger** — "Track every flip with profit math."

Use simple bold text overlays at top, app screenshot below. Apple's required dimensions for 6.7" iPhone: **1290 × 2796 pixels**.

---

## App Store Connect submission checklist

- [ ] Apple Developer Program enrollment ($99/yr)
- [ ] Bundle ID `com.pennyfinder.app` registered in App Store Connect
- [ ] EAS production build (`eas build --platform ios --profile production`)
- [ ] App Store Connect listing created
- [ ] All 8 screenshots uploaded
- [ ] App icon 1024×1024 uploaded
- [ ] Description, subtitle, promotional text, keywords filled in
- [ ] Privacy nutrition labels filled in (use the table above)
- [ ] Privacy policy URL set: https://pennyhunter.store/privacy
- [ ] Support URL set
- [ ] Demo account NOT NEEDED (no login required) — Apple sometimes asks; we don't have one
- [ ] Export Compliance: ITSAppUsesNonExemptEncryption = NO (we use only standard TLS, no proprietary crypto) — set in app.json
- [ ] Submit for review

Apple review: typically 24-72 hours.

---

## Google Play Store checklist

- [ ] Google Play Developer account ($25 one-time)
- [ ] Internal testing track (instant)
- [ ] Closed testing track (no review)
- [ ] Open beta track (no review, public link)
- [ ] Production track (review ~1-3 days for first submission, instant after)
- [ ] EAS production build (`eas build --platform android --profile production`)
- [ ] AAB (app bundle) uploaded
- [ ] All store listing assets uploaded
- [ ] Data Safety form completed
- [ ] Content rating questionnaire (IARC) — answer "no" to all sensitive content questions

---

## Marketing assets to make later

Lower priority but useful for launch:

- App preview video (15-30 sec, .mp4) — shows the actual app in motion
- Press kit (logos, screenshots, founder bio, one-pager)
- Press contacts: TechCrunch shopping vertical, AppSumo, ProductHunt
- Reddit launch post drafts: r/Flipping, r/PennyShopper, r/Couponing
- TikTok demo: 30-second penny-day scan + "PENNY!" haptic confirm
- Email blast to your signup list (the Notify Me form on the landing page)

---

## ITSAppUsesNonExemptEncryption (the export compliance question)

Apple asks every developer this during submission. The answer for Penny Hunter is **NO** because:
- We only use standard TLS for network calls (Apple grants automatic exemption)
- We don't use proprietary cryptographic algorithms
- We don't transmit user-encrypted data outside the app

This is reflected in `app.json` → `ios.infoPlist.ITSAppUsesNonExemptEncryption: false` (added next).
