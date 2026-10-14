# Security

## Retired Matter keys in the git history

This applies to the private working repo (`airplay-manual-vol-private`). The
public repo `airplay-manual-vol` starts from a fresh copy without that history,
so it never contained these files.

In the private repo, commits `a9629c8` through `7ad97a3` (2026-10-13) contain a folder
`matter/wallvol/` with a Matter controller identity: a root key pair,
certificates, and a commissioning passcode. The prototype's Matter bridge
(matter.js) generated it locally the first time it ran, and it was committed
by mistake.

That identity is retired and controls nothing:

- It was deleted and replaced with a new one in `f73f2c3`, before any device
  was paired with it. No plug, light or other device has ever trusted it.
- It was never used with any real device, account or network.
- The `matter/` folder is now ignored by git, so the bridge's current identity
  is never committed.

If a secret scanner flags these files, the alert can be closed as revoked.

## The demo server's API

The prototype server (`wallvol`) controls real devices: speakers, a sauna,
plugs. A review on 2026-10-13 found its API was open: any website open in your
browser could send it commands (for example, start the sauna or erase every
setting), DNS rebinding could read its replies, and with `--lan` anyone on the
network could use it. The Matter bridge on 127.0.0.1:5541 had the same gap.
Fixed on branch `security-hardening`:

- **Host allowlist:** requests must be addressed to 127.0.0.1, localhost, ::1
  or, with `--lan`, this computer's network address (blocks DNS rebinding).
- **JSON and origin:** every change must be `application/json` (a website
  can't send that without the browser asking first) and, if the browser sends
  an Origin, it must be this server's.
- **Per-launch token:** every `/api` call needs `X-Wallvol-Token`. Pages get
  it only when loaded from this computer, or by the phone that opened the
  setup QR code (the code carries it). Scripts read it from
  `credentials/api-token`.
- **Matter bridge:** answers only its own host name and requests carrying a
  secret the server makes at each launch.
- **Device text is text:** error messages from devices (e.g. a Sonos HTTP 500
  body) are cleaned on the server and shown as text on the panel, never as
  HTML.

Tests: `tests/test_security.py`, and the "Security" checks in
`tests/e2e_test.py`.

## Your own setup

Settings the panel creates on your machine (HomePod pairing keys, Matter
identity, HUUM and Traeger sign-ins) live in `~/.wallvol/`, or in ignored
files and folders in the repo when you use `run.sh`. Never commit them.

