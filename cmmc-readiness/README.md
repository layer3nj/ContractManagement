# CMMC Readiness Check

A self-contained, static CMMC Level 2 / CUI readiness self-assessment tool: a landing
page, a multi-step questionnaire with dynamic follow-up questions, a scored results
view, and a shared responsibility matrix. No backend, no build step, no dependencies
&mdash; just HTML/CSS/JS you can drop into any web host or embed in an iframe.

## Files

- `index.html` &mdash; marketing/landing page with the CTA into the tool
- `app.html` + `app.js` &mdash; the questionnaire app (Overview / Questionnaire / Results / Matrix)
- `styles.css` &mdash; all styling, driven by CSS variables

## Customize

1. **Branding** &mdash; edit the CSS variables at the top of `styles.css` (`--color-primary`,
   `--color-navy`, etc.) and the `CONFIG` object at the top of `app.js`
   (`companyName`, `toolName`). Replace the `Your<span>Company</span>` markup in
   `index.html`'s header with your own logo/wordmark.
2. **Questions** &mdash; edit the `QUESTIONS` and `DYNAMIC_QUESTIONS` arrays in `app.js`.
   Each dynamic question has a `triggersOn(boundary)` function that decides when it
   appears based on the "Where is CUI handled today?" dropdowns.
3. **Matrix** &mdash; edit `MATRIX_ROWS` in `app.js`.
4. **Optional platform tips** &mdash; if you offer your own compliant hosting/platform
   option, set `CONFIG.showPlatformTips = true` and reference `CONFIG.platformName`
   in the dynamic questions' `tip` text.

## Run locally

```bash
cd cmmc-readiness
python3 -m http.server 8000
```

Open http://localhost:8000

## Deploy

These are static files &mdash; upload the folder to any static host (S3, Netlify,
GitHub Pages, your existing web server, etc.) or copy it into your site's public
directory.

## Notes

- Nothing is persisted: state lives in memory only and clears on refresh, by design
  (matches the "don't type sensitive data into a lead-gen tool" disclaimer shown in
  the questionnaire).
- Content follows CMMC Level 2 / NIST SP 800-171 practice families at a plain-language
  level; it is guidance only, not a certification determination.
