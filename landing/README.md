# pennyhunter.store landing page

Single-file static site for the marketing/affiliate-validation landing page
at `https://pennyhunter.store`.

## Deploy via Vercel (recommended, free, takes 5 min)

1. Push this folder to a new private GitHub repo (or include it in the
   existing penny-finder-backend repo under `/landing`).
2. https://vercel.com/new → import the repo → Vercel auto-detects static
   site (no build command needed; just serves `index.html`).
3. In Vercel project settings → Domains → add `pennyhunter.store` and
   `www.pennyhunter.store`.
4. At the registrar where you bought `pennyhunter.store`:
   - Set nameservers to Vercel's (instructions appear in step 3) **OR**
   - Add an `A` record pointing the apex `@` to `76.76.21.21` and a
     `CNAME` for `www` → `cname.vercel-dns.com`.
5. Vercel auto-issues an SSL cert. Done.

## Deploy via GitHub Pages (free, also fine)

1. Move `landing/index.html` to a separate repo's root, or to the
   `gh-pages` branch of any repo.
2. Repo Settings → Pages → enable.
3. Add custom domain `pennyhunter.store` → set the registrar's `CNAME`
   for `www` to `<user>.github.io`.

## What this enables

- Skimlinks affiliate signup will accept `pennyhunter.store` as your "site."
- Impact Affiliate (Walmart/Target/CVS programs) will accept the domain.
- Awin, CJ Affiliate, Rakuten — same.
- Looks legit on App Store listing when you eventually submit.

## Edits to make before going live

- Replace `hello@pennyhunter.store` with a real inbox you'll check (or
  set up forwarding via your registrar).
- Add a privacy policy + terms link if Skimlinks asks (they sometimes do).
  A simple `privacy.html` covering "we use AsyncStorage on-device, no
  account, opt-in location, affiliate links may earn commission" is plenty.
