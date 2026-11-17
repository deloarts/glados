# 0010 displays sign in with a device key pair, not a shared secret

- Status: accepted
- Date: 2026-10-30

## context

Wall displays show production data with nobody signed in. They need an identity that survives restarts, can be revoked one by one and never shows up in a URL, a screenshot or a browser history. A secret in the kiosk URL or in browser storage leaks through exactly those, and a shared API key on every display could not be revoked per display. The key router also has routes that accept any valid key without a permission check, so a key handed to displays must not work there. The displays are Raspberry Pis that run glados-terminal, a bridge on `localhost` the kiosk page can call.

## decision

The bridge generates an Ed25519 key pair and keeps the private key; Glados only stores the public key. A display signs in with challenge, sign, session: Glados issues a nonce bound to the public key, the bridge signs it, and Glados answers a 15 minute terminal token signed with a key derived for terminals alone, so it is never accepted as a web session or PAT and a web token is never accepted by the device endpoints. Every device request reloads the terminal, so revoking acts at once. An unknown key registers as pending only with a terminal key, an API key whose service account holds exactly `connect:terminals`, which nothing else can grant and which the key router refuses with 403; a person approves the pending display by typing the code it shows. A known key needs no API key, so revoking terminal keys never cuts off enrolled displays. Only Pis with the bridge are supported.

## consequences

No secret travels in a URL and each display is revoked on its own. A leaked terminal key yields only pending entries, capped and useless without the code on the screen. The price is a bridge on every display, a nonce claim in Redis per sign-in, and clone detection that can only mark a terminal, since an address change looks the same. The protocol, its threat model and the operator duties are in [TERMINAL_INTEGRATION.md](../TERMINAL_INTEGRATION.md).
