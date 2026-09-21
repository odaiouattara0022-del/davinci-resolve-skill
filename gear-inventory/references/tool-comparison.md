# Build or buy: the 2026 landscape

Prices and claims below were checked in September 2026 from the vendors and
review sites linked at the bottom. **Re-check before committing** - asset
software pricing moves, and most vendors quote per-user or per-admin, which is
what actually decides the bill.

## The short answer

| Situation | Use |
|-----------|-----|
| Your own gear, a few dozen to a few hundred items | **This CLI**, or Sortly's free tier if you want a phone app |
| A small crew, gear moving between people daily | **This CLI** + a shared folder / git, or **Shelf** if the crew won't touch a terminal |
| Non-technical crew, bookings weeks ahead, phone-first | **Cheqroom** or **Shelf** |
| You rent gear out and invoice for it | **Rentman** - the others don't do quotes, contracts and rental pricing |
| Corporate IT fleet, laptops and licences | **Snipe-IT** |
| Tens of thousands of items, stocktake in hours not days | Any of the above **+ RFID** (see [labeling.md](labeling.md)) |

## What each one is

**This CLI.** One SQLite file, Python standard library, works offline, no
account, no per-seat cost, full history, agent-drivable via `--json`. You get
data ownership and automation; you do not get a phone app, a booking calendar,
photo galleries or multi-user write concurrency. Two people editing the same
`.db` on a sync folder at the same time will conflict - put it on one machine,
a server, or in git with a discipline of "pull, run, push".

**Sortly** - cloud, photo-first, genuinely pleasant for a solo owner. Free tier
is 100 items and 1 user; paid tiers were quoted at roughly $24/mo (2 users),
$74/mo (5 users) and $149/mo (8 users) billed annually, each with an item cap
and features like role permissions gated to the upper tiers. Great at "what do
I own"; weaker at "who has it and when is it back".

**Cheqroom** - built for exactly this problem (shared AV/production gear,
custody, kits, bookings), phone app that crews actually use. Quoted from about
$184/year on the entry plan, priced **per admin**, with higher Business and
Enterprise tiers. The per-admin model is what to model out before signing.

**Shelf (shelf.nu)** - open source (self-host free, or managed cloud), bookings,
kits, QR labels, mobile app, workspaces that keep one team's gear separate from
another's. The closest thing to "Cheqroom, but you can run it yourself". Needs
someone comfortable deploying a web app.

**Rentman** - event and media production, and the only one here that treats gear
as *rental stock*: quotes, contracts, crew scheduling, sub-hire, availability
across projects. Quoted from about $14/user/month for crew and $19/user/month
for inventory. Overkill unless you rent out.

**Snipe-IT** - free, open source (AGPL, PHP/Laravel), self-hosted or cloud,
mature check-in/check-out with barcodes and QR, licences, consumables,
accessories, full audit trail. Its centre of gravity is IT assets, not camera
kits: no booking calendar, and self-hosting means you own the patching (four
security advisories needed patches during 2025 alone).

## Honest limits of the build-it option

- **No concurrent multi-user writes.** SQLite is fine for one operator at a
  time. A second person scanning gear in at the same moment needs a real
  server - at that point export to Shelf or Snipe-IT rather than fighting it.
- **No phone app.** A phone can scan the QR and open a URL if you host one, but
  out of the box the scanning device is a USB barcode reader plugged into the
  machine running the CLI.
- **No reservation calendar.** `due` dates tell you what is late, not what is
  free next Thursday.
- **You own the backups.** The whole inventory is one file - copy it, or keep it
  in git (see [method.md](method.md)).

If any of those three becomes a daily problem, that is the signal to buy.
`export --out inventory.csv` produces a flat file every tool on this page
imports, so starting here does not lock you in.

## Sources

- [Best Equipment Management Software (2026) - Shelf](https://www.shelf.nu/blog/best-equipment-management-software)
- [Cheqroom pricing - Capterra](https://www.capterra.com/p/140824/CHEQROOM/)
- [Rentman pricing - Capterra](https://www.capterra.com/p/144616/Rentman/)
- [Sortly alternative comparison - Shelf](https://www.shelf.nu/alternatives/sortly)
- [Snipe-IT product features](https://snipeitapp.com/product)
- [Snipe-IT review 2026 - sobrii](https://sobrii.io/blog/snipe-it)
- [Open source Snipe-IT alternative - Shelf](https://www.shelf.nu/alternatives/snipe-it)
- [shelf.nu on GitHub](https://github.com/shelf-nu/shelf.nu)
