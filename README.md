# Discord Alternative Tracker

Tracks Discord alternatives. The site is hosted on Cloudflare Pages and the API runs on a Cloudflare Worker.

## Layout

- `data/` - the source workbook, `discord_alternatives_categorized.xlsx`
- `scripts/build_data.py` - converts the workbook into `pages/public/data.js`
- `pages/` - the static site deployed to Cloudflare Pages (`wrangler.jsonc`, files in `public/`)
- `worker/` - the API Worker (`wrangler.jsonc`, source in `src/`)

The site is plain HTML, CSS and JavaScript with no build step and no dependencies. It reads `data.js` and renders every sheet as a table with one column for Discord and one for each platform picked from the dropdowns, up to three at a time.

## Setup

Requires Node.js 20 or newer.

```
npm install
npm run worker:types
npm run login
```

`npm run worker:types` generates `worker/worker-configuration.d.ts`, the editor types for the Worker. It is not committed, so rerun it after changing `worker/wrangler.jsonc` or updating Wrangler.

`npm run login` opens a browser and links Wrangler to your Cloudflare account. Run it once per machine. `npm run whoami` shows which account is linked.

For CI or scripted deploys, copy `.env.example` to `.env` and set `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` instead of logging in.

## Updating the data

Edit the workbook in `data/`, then regenerate the data file and commit both:

```
npm run data
```

This needs Python 3 with the `openpyxl` package (`pip install openpyxl`). The script keeps the sheet order and grouping from the workbook's Sheet Directory tab, so adding a sheet there is enough for it to appear on the site.

## Develop

```
npm run worker:dev
npm run pages:dev
```

## Deploy

```
npm run worker:deploy
npm run pages:deploy
```

The Pages project already exists on the account, so `pages:deploy` publishes straight to it. If you ever need to recreate it on a fresh account, create it once first, then deploy as usual:

```
npx wrangler --cwd pages pages project create discord-alternative-tracker --production-branch main --force
```

The `--force` flag makes current Wrangler versions create a classic Pages project instead of a Worker with static assets. It is only needed for that one command.

## License

GPL-3.0. See `LICENSE`.
