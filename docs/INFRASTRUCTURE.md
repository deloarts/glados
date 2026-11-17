# infrastructure environment

This document describes the corporate environment Glados integrates with and the constraints it places on a deployment. It records patterns, not inventory: hostnames, IP addresses, site codes and internal DNS namespaces are held only in the private deployment configuration (`.env`, the admin settings and IT's own records). The placeholders `corp.example`, `CORP` and `<site>-dc-NN` stand in for the real names throughout.

- [infrastructure environment](#infrastructure-environment)
  - [1 dns](#1-dns)
  - [2 active directory](#2-active-directory)
  - [3 mail](#3-mail)
  - [4 certificates](#4-certificates)
  - [5 network egress and exposure](#5-network-egress-and-exposure)
  - [6 deployment constraints](#6-deployment-constraints)
  - [7 verifying a candidate host](#7-verifying-a-candidate-host)

## 1 dns

The primary domain (`corp.example`) is served by two independent DNS views that return different answers for the same name.

- The **public view** is an authoritative zone at an external DNS provider. It holds only internet-facing records: the marketing website (on a third-party CDN), mail routing, and verification and policy TXT records (SPF, DMARC and SaaS domain-verification tokens). Internal names are absent, so a domain controller queried from the internet resolves to `NXDOMAIN`.
- The **internal view** is Active Directory-integrated DNS, reachable only from the corporate network, which resolves infrastructure hosts to private (RFC1918) addresses.

A name such as `<site>-dc-NN.corp.example` therefore resolves to a private address on the LAN and to nothing from outside. A host on the public internet cannot reach an internal service by name, and a hardcoded private address is not routable across the internet. The deployment constraints in [section 6](#6-deployment-constraints) follow from this.

## 2 active directory

The AD forest is named after the public domain (`corp.example`), as Microsoft recommends. The NetBIOS short name differs from the DNS name, so bind usernames take the form `CORP\username` rather than `username@corp.example`; the short name is the value of the application's `ldap_domain` setting (see [admin_settings/auth.py](../backend/src/modules/platform/domain/entities/admin_settings/auth.py)).

The directory is large and multi-site: dozens of domain controllers across many sites, named per site (`<site>-dc-NN`). Every controller advertises LDAP (389), LDAPS (636), Kerberos (88) and global-catalog (3268) service records.

Glados binds against one configured domain controller over LDAPS (636) with a direct simple bind, without a service account and without searching the directory for the user (see the [LDAP notes](/docs/OPERATIONS.md#55-ldap-certificate-verification)). Because the controller is configured rather than located through DNS, pick one that is reachable from, and close to, the deployment's site. The `ldap_timeout_seconds` setting bounds the bind, so an unreachable controller fails quickly instead of holding one of the worker's offload threads on every login (ldap3 is blocking and runs off the event loop).

## 3 mail

Outbound mail for the domain runs through Microsoft 365 (Exchange Online): the public MX record points at `*.mail.protection.outlook.com`, autodiscover points at Outlook, and SPF authorises the Microsoft 365 include alongside the corporate egress addresses. The application's SMTP relay is therefore one of two options.

- **Microsoft 365 directly** needs an authenticated submission mailbox or an approved connector with the sending address allow-listed at the tenant. It presents a publicly trusted certificate, so `verify_certificate` stays on.
- **An internal relay** may present a certificate from the internal CA ([section 4](#4-certificates)). The application's trust store must then include the internal root, or `verify_certificate` must be turned off as the documented opt-out ([OPERATIONS.md §5.4](/docs/OPERATIONS.md#54-smtp-certificate-verification)).

Confirm the chosen relay with *Admin Settings → Mail → Test connection* before enabling it for live mail.

## 4 certificates

IT issues certificates centrally from two distinct trust domains.

- The **internal CA** is an enterprise certificate authority. Domain-joined machines trust its certificates automatically, while non-domain hosts and external browsers do not unless the internal root is added to their trust store. It suits internal-only names such as LDAPS endpoints and an internal SMTP relay.
- A **publicly trusted certificate** is required for any internet-facing name, such as the application's own HTTPS hostname, which external browsers must trust without the internal root.

When IT provides a certificate, confirm which trust domain issued it and which names it covers, then install it at the reverse proxy as described in [INSTALLATION.md §6](/docs/INSTALLATION.md#6-ssl-termination). The application itself does not terminate TLS.

## 5 network egress and exposure

Outbound internet traffic leaves through a central corporate firewall with a small set of static public addresses, the same ones SPF authorises for mail. Every outbound request of the application (webhook deliveries, Microsoft 365 submission) comes from that address set, which matters where a destination allow-lists by source IP.

By default there is no inbound path from the internet to a host on the network. Exposing Glados externally is a separate, deliberate step, such as a reverse proxy in a DMZ, a firewall exception or a Cloudflare Tunnel ([INSTALLATION.md §6.8](/docs/INSTALLATION.md#68-alternative-cloudflare-tunnel)), and is independent of the internal DNS and directory reachability above.

## 6 deployment constraints

The directory dependency anchors production to the corporate network. Whoever owns the host and wherever it stands, LDAP authentication has two requirements:

1. The host uses the internal DNS view, so that `corp.example` names resolve to their private addresses.
2. The host has a network route to a domain controller on port 636, through the same LAN or an IT-provisioned site-to-site link or SD-WAN into it.

| Host placement | LDAP | Notes |
| --- | --- | --- |
| On-premises, network-attached | Supported | Internet exposure is arranged separately (reverse proxy or tunnel). |
| Off-site, joined to the corporate WAN by IT | Supported | Common for company-managed hosts. Each login crosses the link, so its reliability decides login availability. |
| External VPS, not network-attached | Not supported | The domain controller is unreachable; only local password and TOTP accounts work. |

Host ownership decides what IT is willing to connect to the corporate network, not whether the network path exists. The deciding question for any candidate host is whether it resolves internal DNS and reaches a domain controller on port 636.

## 7 verifying a candidate host

Confirm the above from the candidate host before committing to it. A reachability check needs no credentials:

```bash
python3 -c "import socket; socket.create_connection(('<site>-dc-NN.corp.example', 636), timeout=5); print('DC reachable on 636')"
```

If it succeeds, a local, uncommitted test script using `ldap3` or the standard library can confirm a full LDAPS bind and directory read, which exercises name resolution, routing, firewall, TLS and credentials together. Put the real domain controller name, domain and credentials only in that local script and keep them out of committed files.
