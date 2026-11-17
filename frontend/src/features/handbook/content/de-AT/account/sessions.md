---
title: Sitzungen
summary: Wo du angemeldet bist, welche Geräte den Zwei-Faktor-Code überspringen und wie du beides beendest.
sourceRefs:
  - backend/src/modules/platform/application/use_cases/session/manage_sessions.py
  - backend/src/modules/platform/application/use_cases/session/manage_trusted_devices.py
  - backend/src/modules/platform/domain/services/session_rules.py
  - frontend/src/core/session/userActivity.ts
  - backend/src/modules/platform/application/use_cases/auth/totp_login.py
  - backend/src/modules/platform/application/use_cases/user/update_user.py
  - backend/src/modules/platform/application/use_cases/user/force_logout_user.py
lastVerified: 2026-11-12
---

Konto, **Sitzungen** zeigt zwei Listen. **Aktive Sitzungen** sind die Orte, an denen du gerade angemeldet bist. **Vertrauenswürdige Geräte** sind die Browser, die bei der Anmeldung den Zwei-Faktor-Code überspringen dürfen. Beides ist getrennt: Meldest du ein Gerät ab, bleibt es vertrauenswürdig, und die nächste Anmeldung dort verlangt keinen Code.

## Deine Sitzungen {#sessions}

Jede Zeile von **Aktive Sitzungen** zeigt das **Gerät**, wie sich sein Browser nennt, die **IP-Adresse**, von der es sich angemeldet hat, wann es **Angemeldet am** war und wann **Zuletzt aktiv**. Die Sitzung, die du gerade verwendest, trägt das Etikett **Dieses Gerät**. Die Liste zeigt nur Sitzungen, die noch gelten.

## Warum eine Sitzung von selbst endet {#idle}

Eine Sitzung endet, wenn du sie länger in Ruhe lässt, als die Leerlaufgrenze erlaubt, die eine Administration festlegt. Jeder Klick, jede Taste, jedes Scrollen oder Tippen auf einer Seite startet diese Uhr neu, darum wirst du nie mitten in der Arbeit abgemeldet, auch nicht, während du einen langen Text schreibst. Was Glados von selbst tut, etwa nach Benachrichtigungen schauen, zählt nicht, darum läuft eine offen gelassene Seite ab wie jede andere. Egal wie aktiv du bist, endet jede Sitzung außerdem 30 Tage nach der Anmeldung, oder nach der Zahl der Tage, die eine Administration gewählt hat, und du meldest dich dann neu an.

## Eine Sitzung abmelden {#revoke}

**Abmelden** in einer Zeile beendet diese Sitzung sofort, und das Gerät muss sich neu anmelden. Bei deiner eigenen Sitzung meldet es dich hier ab, und die Rückfrage warnt dich. **Andere Sitzungen abmelden** beendet alle Sitzungen außer der, die du verwendest. Nimm das, nachdem du dich an einem fremden Computer angemeldet hast, oder wenn dir eine Zeile unbekannt vorkommt.

## Vertrauenswürdige Geräte {#devices}

Meldest du dich mit Zwei-Faktor-Authentifizierung an, kannst du **Auf diesem Gerät 30 Tage nicht mehr fragen** anhaken, mit der Zahl der Tage, die eine Administration festgelegt hat. Nachdem der Code angenommen ist, wird dieser Browser ein vertrauenswürdiges Gerät und überspringt den Code, bis das Vertrauen abläuft. Die Liste zeigt, seit wann jedes Gerät vertraut ist, wann es **Zuletzt verwendet** wurde und wann es **Läuft ab**. Hat die Administration 0 Tage eingestellt, wird das Häkchen nicht angeboten. Ein vertrauenswürdiges Gerät bleibt vertrauenswürdig, wenn du dich abmeldest, genau dafür ist es da.

## Ein vertrauenswürdiges Gerät entfernen {#untrust}

**Entfernen** in einer Zeile beendet das Vertrauen dieses Browsers, er verlangt bei der nächsten Anmeldung wieder einen Code. **Alle entfernen** tut das für alle Geräte. Ein Gerät, das du nicht mehr hast, solltest du entfernen und nicht nur abmelden.

## Was sie ohne dich beendet {#automatic}

Änderst du dein eigenes Passwort, enden alle anderen Sitzungen, alle vertrauenswürdigen Geräte werden entfernt und alle [Zugriffstoken](/handbook/account/access-tokens) widerrufen, während die Sitzung, in der du es geändert hast, bleibt. Ändert eine Administration dein Passwort, enden alle deine Sitzungen, und deine Token werden ebenfalls widerrufen. Schaltest du die Zwei-Faktor-Authentifizierung aus, oder setzt eine Administration sie zurück, werden alle vertrauenswürdigen Geräte entfernt. Meldet eine Administration dein Konto überall ab, enden deine Sitzungen, vertrauenswürdigen Geräte und [Zugriffstoken](/handbook/account/access-tokens).

## Beispiele

**Ein fremder Computer.** Du hast dich am Schreibtisch einer Kollegin angemeldet und das Abmelden vergessen. Zurück an deinem Computer klickst du auf **Andere Sitzungen abmelden**, und der fremde Computer ist sofort abgemeldet.

**Ein verlorenes Handy.** Du klickst in der Zeile des Handys auf **Abmelden** und bei seinem vertrauenswürdigen Gerät auf **Entfernen**. Wer es findet, braucht dein Passwort und einen neuen Code.

**Ein neues Passwort.** Du änderst dein Passwort am Bürocomputer. Dein Laptop zu Hause verlangt beim nächsten Mal eine neue Anmeldung mit Code.
