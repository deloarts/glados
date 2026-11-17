---
title: Drucker
summary: Wie du einen Etiketten- oder Dokumentdrucker anlegst, prüfst, ob er funktioniert, ihn außer Betrieb nimmst und siehst, was er gedruckt hat.
sourceRefs:
  - backend/src/modules/quality/application/use_cases/printer/create_printer.py
  - backend/src/modules/quality/application/use_cases/printer/test_print_printer.py
  - backend/src/modules/quality/application/use_cases/printer/get_printer_status.py
  - backend/src/modules/quality/domain/services/printer_rules.py
  - backend/src/modules/quality/application/use_cases/print_document/get_print_jobs.py
  - backend/src/modules/quality/domain/services/printer_host.py
lastVerified: 2026-11-10
---

Unter Ressourcen listet **Drucker** jeden Drucker, an den Glados senden kann. Etiketten gehen an Etikettendrucker, Berichte und Laufzettel an Dokumentdrucker.

## Etikettendrucker und Dokumentdrucker

**Art** bestimmt, was ein Drucker bekommt. Ein Drucker der Art **ZPL-Etikett** nimmt Etiketten in der Etikettendruckersprache ZPL an und wird über die **Übertragung** **Raw (JetDirect)** erreicht, meist auf Port 9100. Ein Drucker der Art **IPP-Dokument** nimmt PDF-Dateien wie Berichte und Laufzettel an und wird über **IPP** erreicht, meist auf Port 631. Wechselst du die **Art**, stellen sich die **Übertragung** und der übliche Port passend um; einen Port, den du selbst eingetragen hast, behält er.

## Einen Drucker anlegen

Klick auf **Neuer Drucker** und füll **Name**, **Art**, **Host** und **Port** aus, eine Zahl von 1 bis 65535. Die übrigen Felder sind optional. **Host** ist der Netzwerkname oder die Adresse des Druckers, und Glados lehnt Adressen des Servers selbst und seiner eigenen Dienste ab. **Zeitlimit (Sekunden)** ist, wie lange Glados auf eine Antwort wartet, standardmäßig 5.

Bei einem Etikettendrucker ist **Druckkopf-DPI** die Auflösung seines Druckkopfs, standardmäßig 300. Der **Format-Umwandlungsfaktor** muss zur Einstellung FORMAT UMWANDELN am Bedienfeld des Druckers passen; ein falscher Wert druckt Etiketten in falscher Größe. Bei einem Dokumentdrucker beginnt der **IPP-URI-Pfad** mit "/" und **Standardmedium** nennt das Papier, das der Drucker nimmt, wenn nichts anderes verlangt wird.

**Standort**, **Hersteller**, **Modell**, **Firmware** und **Notiz** beschreiben den Drucker nur. **Verbrauchsmaterial** listet die Zukaufteile, die er verbraucht, etwa Etiketten, Farbband oder Toner.

## Deaktivierte und archivierte Drucker

Ein Drucker, der nicht **Aktiviert** ist oder archiviert wurde, bekommt nichts. Etiketten und Laufzettel für ihn werden nicht gesendet; sie stehen mit dem Grund als fehlgeschlagen in seinem **Druckverlauf**. Schalt **Aktiviert** aus, solange ein Drucker repariert wird, und archivier ihn, wenn er endgültig weg ist. **Alle Drucker deaktivieren** auf den Seiten **Druck-Etiketten** und **Laufzettel** schaltet alle Drucker auf einmal aus.

## Einen Drucker prüfen

**Testdruck** schickt ein kleines Test-Etikett oder ein einseitiges PDF mit deinem Benutzernamen und der Uhrzeit. Der Testdruck erreicht auch einen deaktivierten Drucker, so prüfst du einen neuen Drucker, bevor du ihn aktivierst. **Druckerstatus** fragt den Drucker nach seinem Zustand und zeigt seine **Identität** und seinen **Status**, oder "Drucker konnte nicht erreicht werden.", wenn er nicht antwortet. Eine Antwort, die nicht von einem Etikettendrucker kommt, wird nicht angezeigt, und der Status sagt das.

Ist **Aktionen anzeigen** eingeschaltet, hat jede Zeile Knöpfe für beide Prüfungen, **Drucker bearbeiten** und **Archivieren** oder **Wiederherstellen**. Ein Rechtsklick auf eine Zeile bietet dieselben Aktionen und den **Druckverlauf**. Die Tabelle lässt sich nach **Art** oder **Standort** gruppieren.

## Druckverlauf {#history}

Der **Druckverlauf** listet, was an den Drucker ging, mit **Erstellt**, **Dokument**, **Datensatz**, **Auslöser**, **Kopien**, **Status** und **Ausgeführt von**. **Auslöser** sagt, ob der Druck **Automatisch** oder **Manuell** war, und **Status** ist **Wird gedruckt**, **Gesendet** oder **Fehlgeschlagen**; zeig auf einen fehlgeschlagenen Status, um den Grund zu lesen. Wie Berichte gedruckt werden, steht in [Berichte exportieren und drucken](/handbook/resources/report-export).

## Wer was darf

Zum Anlegen, Bearbeiten, Archivieren und Wiederherstellen eines Druckers brauchst du **Drucker und Druckvorlagen schreiben**. **Testdruck** und **Druckerstatus** brauchen **Dokumente drucken**, der **Druckverlauf** braucht **Einstellungen lesen**. Ohne sie sind **Neuer Drucker**, **Drucker bearbeiten**, **Testdruck**, **Druckerstatus**, **Druckverlauf**, **Archivieren** und **Wiederherstellen** deaktiviert, und ein Tooltip nennt die fehlende Berechtigung.

## Beispiele

**Ein neuer Etikettendrucker.** Klick auf **Neuer Drucker**, gib Zebra Halle 2 ein, wähl **ZPL-Etikett**, trag seine Adresse ein und lass Port 9100. Schalt **Aktiviert** aus, klick auf **Testdruck**, prüf, ob das Etikett in der richtigen Größe herauskommt, und schalt dann **Aktiviert** ein.

**Ein Drucker in Reparatur.** Schalt **Aktiviert** beim Bürodrucker aus. Die Los-Laufzettel für ihn werden nicht gedruckt und stehen als **Fehlgeschlagen** in seinem **Druckverlauf**, so druckst du sie nach, sobald er wieder da ist.
