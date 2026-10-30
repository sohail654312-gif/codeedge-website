# Codeedge private SEO reporting — setup guide

This repository is **PUBLIC**. Never add private analytics, search queries, API keys, Google service-account credentials or report artifacts to this repository, a public GitHub Actions job, GitHub Pages, or frontend code.

## What is implemented

- Read-only Google Search Console API: Google web-search clicks, impressions, top queries and top pages.
- Read-only GA4 Data API: active users, sessions, page views and event counts (subject to visitor consent).
- Read-only Bing Webmaster JSON API: Bing clicks, impressions and queries.
- Previous **28 full days ending 3 days ago**. Missing credentials are reported as \`authorization_required\`, never as zero traffic.
- A local Markdown/JSON report written only to a **private directory outside the public website repository**.

## Remaining owner-only authorizations

**Google** (one-time):
1. Open an existing Google Cloud project, or create one if necessary after reviewing any billing implications. Enable the **Google Search Console API** and **Google Analytics Data API**.
2. Create a dedicated Google service account and privately store its JSON credential. In the verified Search Console property \`https://codeedge.online/\`, grant the service-account email the least user permissions needed for search performance reporting (never Owner).
3. In Google Analytics, grant that same service-account email **Viewer** access to Codeedge's GA4 property. Find and record the **numeric property ID**. The site's tracking ID \`G-129XGJDT47\` is a measurement ID, not the GA4 property ID.

**Bing** (one-time):
1. Sign in at https://www.bing.com/webmasters and select your verified Codeedge website.
2. Under **Settings > API Access**, generate or retrieve your own API key. Bing's API key is user-level and may access other sites; treat it as secret.
3. Store the key securely, never in GitHub source, email, screenshots or ChatGPT messages.

**Do not share any API key or JSON credential in chat.** If you use a credential vault, grant the private runtime access without copying the secret into prompts.

## Run in an owner-controlled PRIVATE environment

Python 3.12+, \`google-auth\` and \`requests\` are required for the Google service-account token:

\`\`\`sh
python -m pip install google-auth requests
python scripts/seo_traffic_report.py --output-dir /private/codeedge-seo
\`\`\`

Provide these **private environment variables** through your secret vault:
- \`GOOGLE_SERVICE_ACCOUNT_JSON\` (complete credential JSON)
- \`GA4_PROPERTY_ID\` (numeric)
- \`BING_WEBMASTER_API_KEY\`

The output is \`report.json\` and \`report.md\` in the private folder. The script exits code 2 if a source lacks authorization; it does not forge data. Never upload these reports to this *public* repository or public Actions artifacts. Read-only APIs do not automatically grant this regular ChatGPT conversation access to the private data; a separately authorized connector or controlled report share is still required.

## Local safety tests, no credentials or network

\`\`\`sh
python -m unittest discover -s tests -p 'test_seo_traffic_report.py' -v
\`\`\`

The GitHub workflow runs **only the fake-data tests**, not the actual credentialed reporting job.

## Notes

- Google Search Console impressions and clicks differ from GA4 sessions and visitors.
- Bing reporting may include web, AI chat, images and other verticals.
- Tracking a phone/WhatsApp click does not prove a customer converted.
- New sites may have little data; reporting can lag.
- This script never updates site settings, rankings, SEO metadata, Ads campaigns or Bing/Google accounts.

Official documentation: 
- https://developers.google.com/webmaster-tools/v1/searchanalytics/query
- https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/properties/runReport
- https://learn.microsoft.com/en-us/bingwebmaster/getting-access
- https://learn.microsoft.com/en-us/dotnet/api/microsoft.bing.webmaster.api.interfaces.iwebmasterapi.getrankandtrafficstats?view=bing-webmaster-dotnet
