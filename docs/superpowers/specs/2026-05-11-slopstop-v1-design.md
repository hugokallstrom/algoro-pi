# slopstop v1 — hardened Pi appliance for self-imposed website blocking

**Status:** design (pre-implementation)
**Date:** 2026-05-11
**Working title:** "slopstop" — rename throughout once brand is chosen.

## Summary

A pre-configured Raspberry Pi appliance that makes a chosen set of websites unreachable for every device on the buyer's home network. DNS-level blocking, set once, enforced always. The hardware is the commitment device: meaningful friction (physical button + cooldown) to ever change the configuration.

Sold in Sweden first as a finished product, founder-fulfilled. EU compliance scoped to a single country for the beta.

## Problem

Every existing self-control tool can be disabled in under 30 seconds by the person who wants to be blocked:

- App-level blockers (Cold Turkey, Opal, Freedom, one sec) — uninstall the app.
- Cloud DNS (NextDNS, ControlD) — toggle the toggle.
- Pi-hole — log in, click "disable for 5 minutes."
- iOS Screen Time — multiple known trivial bypasses; adults rarely apply it to themselves.

Bypass-resistance is the missing primitive. A device the user *physically* cannot disable in 30 seconds is qualitatively different from any software solution.

## Target user (v1)

Adults who have already opted out — or are opting out — of smartphone slop. Typically dumb-phone users (Light Phone, Wisephone, Brick, basic Nokia). Their phone is solved. Their laptop, tablet, smart TV, and game console are not. They are willing to pay €89–€109 for a plug-and-play box that removes those sites from their network entirely.

**Not v1 targets:** parents, kids, schools, smartphone users who haven't downgraded, US buyers.

## Positioning

*"Make your home network a slop-free zone."*

Sits alongside the digital-minimalism movement, not the productivity-app market. Marketed adjacent to dumb-phone communities (r/dumbphones, Light Phone, etc.). Privacy-by-design (local-only DNS, OSS firmware) is a real benefit and a marketing surface — EU buyers care.

## Product surface

### Block model

- Always-on DNS-level blocking of a chosen set of sites.
- No timers, no schedules — the answer is no.
- Curated presets at setup: *Hard Mode*, *Social Only*, *Social + News*, *Custom*.
- User may edit the list later, subject to the lock model.

### Lock model (v1: solo only)

To change the blocklist, disable the service, or unblock a site, the user follows a two-touch sequence:

1. Request the change in the web UI. UI tells the user: "press the physical button to begin a cooldown of N minutes."
2. Press the physical button → cooldown starts. LED indicates cooldown is active. Pending change is held in a queue.
3. After cooldown elapses, LED indicates "ready to confirm."
4. Press the physical button **again** to commit the change.

If step 4 is not performed within a confirm window (e.g. 1 hour after cooldown ends), the pending change is discarded silently.

The default cooldown is 30 minutes, configurable at first setup. Reducing the cooldown later itself requires the cooldown to elapse — you can't shortcut your way to a shorter cooldown.

Two touches are deliberate: the first lets the user commit while still feeling the urge; the second forces a deliberate decision *after* the urge has passed. A single-touch-then-wait pattern would let an impulsive request silently complete later, which defeats the device's purpose.

Partner mode (delegate the unlock password to a trusted third party) is **deferred to v2**.

### Setup UX (the differentiator)

1. User plugs in power + ethernet. LED indicates ready.
2. User connects to the Pi's setup WiFi (SSID like `slopstop-XXXX`) or scans the QR code on the box.
3. A mobile-friendly captive web wizard runs through:
   - Pick preset (or custom list)
   - Set cooldown duration
   - Auto-detect router brand from MAC OUI / DHCP signals; provide tailored "set this Pi as your DNS" instructions, with a manual fallback
4. Wizard confirms blocking is live by issuing a test DNS request to a blocked domain.
5. Done. Target: under 5 minutes from box opening to working block.

### Day-to-day config UI

A local web page at the Pi's IP. Shows current status, the blocklist, recent block events. Any editing action triggers the lock model (button + cooldown).

## Architecture

### Hardware

- **Primary:** Raspberry Pi Zero 2 W
- **Fallback SKU:** Pi 3A+ or generic SBC (in case of Pi shortage — recent history makes this likely)
- Custom or off-the-shelf enclosure with:
  - Multi-color status LED
  - Single tactile button (lock-model actions)
- USB-C power input
- Ethernet preferred (USB-Ethernet adapter or HAT); WiFi fallback
- Pre-flashed, sealed SD card. Buyer never touches a terminal or imager.

### Software stack

- **DNS resolver:** Unbound + dnscrypt-proxy with curated blocklist
- **Admin web app:** small FastAPI backend + HTMX or SvelteKit frontend, served locally
- **Setup wizard:** captive-portal-style app served on the setup WiFi
- **Blocklist update channel:** signed pulls from a curated update server
- **Button + LED daemon:** Python service handling GPIO + cooldown state

### Data flow

- DNS query from any LAN device → Pi resolver → blocklist check → resolve or return NXDOMAIN
- Zero telemetry. Zero phone-home except blocklist update fetches.
- Update fetches present a per-device signed token tied to the device serial. Server logs the fetch (proves "device alive") but stores no IP, no MAC, no DNS queries, no user identity beyond the serial. This token also gates entitlement to the paid update subscription.
- All state local: SQLite for config, flat file for blocklist.

### Component boundaries

- **Firmware (OSS):** DNS stack config, admin web app, setup wizard, button/LED daemon. License: AGPLv3 (protects against forks running as paid services).
- **Proprietary:** curated blocklist contents, setup wizard polish/copy/UX assets, brand assets, the blocklist update server.

The OSS firmware can be audited and re-flashed by anyone who wants to. The curated blocklist + setup polish are the moat.

## Compliance (EU, Sweden beta)

- **CE marking + RED self-declaration** for the assembled product. Pi Zero 2 W is already CE/RED-compliant as a module; we sign the Declaration of Conformity for the combined product. Plan: produce technical file + DoC before first commercial sale.
- **WEEE producer registration** in Sweden only for beta. Expand per country as we add countries.
- **Statutory consumer rights:** 2-year warranty + 14-day right of withdrawal. Build into pricing.
- **VAT:** Swedish VAT only for beta. Register for OSS once we sell cross-border.
- **PSU:** ship separately sourced CE-marked EU-plug USB-C PSU. Do not homebrew power.
- **Pi sourcing:** EU-based distributors (Welectron DE, Reichelt DE, Kubii FR, Sertronics BE) to avoid Brexit customs friction.
- **GDPR:** v1 has no cloud component handling personal data; the blocklist update server fetches are anonymous. No GDPR data-processing footprint in v1.

## Business model

- **Hardware:** one-time sale, working range €89–€109 incl. VAT
- **Optional subscription:** €3–€5/mo for ongoing curated blocklist updates. Without it, the user keeps the last-pulled list — device still works, just goes stale as social CDNs shift.
- **Open-core firmware** — privacy-conscious buyers can audit and self-host the update server if they want to.
- **BOM target:** €25–€35 fully landed (Pi, enclosure, PSU, SD card, cable, packaging). Margin sufficient to absorb a meaningful support load.

## Go-to-market staging

### Phase 0 — Founder-fulfilled beta (20–50 units, Sweden only)

- Direct sale via landing page + Stripe / Klarna
- Hand-packed from home
- Direct customer conversations on every sale
- Validates: setup success rate without support, real BOM, support volume, the "I tried everything else and only this stuck" claim

### Phase 1 — Small-batch domestic (200–500 units, Sweden)

- Same as Phase 0 plus a basic 3PL or self-managed shipping setup
- Wizard available in Swedish + English

### Phase 2 — Regional expansion (target DE, NL, DK)

- OSS VAT registration
- Multi-language wizard
- WEEE registration in expansion countries
- 3PL operationally proven

### Phase 3 — EU-wide

Out of scope for this spec.

## Out of scope for v1

- Mobile cellular bypass (target user has a dumb phone)
- Partner unlock mode (deferred to v2)
- Multi-user / kid profiles
- Cloud DNS / works-anywhere mode
- Parental controls dashboards
- iOS Screen Time integration
- US market
- Multi-country sales
- Mobile companion app
- Telemetry / usage analytics from the device

## Open decisions (parked, not blocking implementation)

- Final brand name (working title "slopstop")
- Exact enclosure: off-the-shelf vs custom-injection-molded (off-the-shelf for beta, custom later)
- Whether the curated blocklist is community-editable or strictly curated (default: strictly curated for v1, OSS list contributions accepted)
- AGPLv3 vs MIT for firmware license (current default: AGPLv3)
- Whether to offer an "emergency unlock" override (current default: no — defeats the purpose)
- Final cooldown default (proposing 30 minutes)
- Whether ethernet adapter ships in the box or is BYO (proposing: in the box, simplifies setup)

## Success criteria (v1 beta)

- 20+ units shipped in Sweden within 60 days of beta opening
- ≥80% of buyers complete setup without contacting support
- ≥70% of buyers still have the device active at 30 days, measured by anonymous blocklist-update fetches from the device's serial-bound update token (server-side log only, no user identification)
- ≤10% return rate
- Either strong qualitative confirmation of "I tried everything else, this is the one that stuck" — or strong disconfirmation, equally valuable

The 30-day-active metric is the only externally observable signal from the device. It tells us "the box is still plugged in and pulling updates" — not what is or isn't being blocked. No usage data, no DNS query logging, no telemetry beyond that single signed update fetch.

## Why this can work

- **Founder-market fit:** founder is the user.
- **Bypass-resistance is structurally underserved.** Every existing tool fails the same way; hardware-as-commitment-device fixes it by construction.
- **Riding a real trend.** Dumb-phone movement is small but growing and well-defined. v1 doesn't need a huge market — a few hundred Swedish customers proves the thesis.
- **EU privacy positioning aligns with the product design.** Local-only, OSS, no telemetry isn't a marketing pose — it's the actual architecture.
- **Hardware ops staged honestly.** Founder-fulfilled beta caps the operational risk; commit to a 3PL only after demand is proven.

## Why this might not work (risks to track)

- **Market size.** Dumb-phone-adjacent buyer pool may be too small even in EU. Mitigation: spec includes early customer-conversation phase; if the pull isn't there, kill it before scaling.
- **Pi supply shocks.** History of shortages. Mitigation: fallback SKU pre-designed.
- **Support tax.** Non-technical buyers will email about WiFi, DNS, router weirdness. Mitigation: budget 1 ticket per 10 units; setup wizard auto-detects router brand to head off the most common questions.
- **Bypass via router reset.** A determined user can reset their router DNS in 60 seconds. Mitigation: this is acceptable — the friction is the product, not absolute prevention. Anyone resetting their router has clearly made a deliberate choice, not an impulsive one.
- **Compliance surprise.** Hardware compliance has unknown unknowns. Mitigation: single-country beta limits the blast radius; consult a Swedish compliance contractor before first commercial sale.
