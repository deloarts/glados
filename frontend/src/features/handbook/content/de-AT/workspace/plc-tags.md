---
title: SPS-Variablen
summary: Wie die SPS-Variablen einer Maschine aus ihren Geräten entstehen, wie du sie korrigierst und ergänzt und wie sie exportiert werden.
sourceRefs:
  - backend/src/modules/workspace/domain/services/plc_naming.py
  - backend/src/modules/workspace/application/use_cases/plc_environment/tags.py
  - backend/src/modules/workspace/domain/services/plc_environment_rules.py
lastVerified: 2026-11-10
---

**SPS-Variablen** im Reiter **Geräte** listet jede Variable der Maschine, gebildet aus den Signalen ihrer Geräte, gefolgt von den Variablen, die du von Hand ergänzt. Die Liste folgt den Geräten, ein umbenanntes Gerät benennt also sofort seine Variablen um, und der SPS-Programmierer bekommt eine Tabelle, die zu den Plänen passt.

## Wie eine Variable entsteht

Eine Variable beginnt mit dem Präfix ihres Signaltyps, etwa di_ für einen digitalen Eingang oder dq_ für einen digitalen Ausgang, und ein Sicherheitssignal bekommt das Sicherheitspräfix seines Typs, etwa fdi_. Dann folgt der Gerätename, umgeschrieben nach der Zeichenumwandlung der SPS-Umgebung, sodass aus ü ein ue und aus Leerzeichen Unterstriche werden. Am Ende steht die **Variablenendung** des Signals, wenn es eine hat, sonst der SPS-Name seiner Stellung (der Zustand bei einem Eingang, der Befehl bei einem Ausgang), sonst der **SPS-Name** des Signals seines Gerätetyps, das es wählt, etwa eines Störungseingangs, sonst die Bedeutung des Signals. Die SPS-Namen der Stellungen und Signale legst du beim Gerätetyp fest. Die Maschinennummer ist nie Teil einer Variable.

Die **SPS-Umgebung** des Produkts bestimmt Präfixe, Umwandlung, **Maximale Variablenlänge** und Export. Ohne eigene Wahl verwendet ein Produkt die Standardumgebung. Wie du eine Umgebung einrichtest und als Datei in eine andere Installation mitnimmst, steht unter [Gerätelisten](/handbook/resources/product-devices#plc-environments).

## Hinweise in der Liste

**Zu lang** markiert eine Variable, die länger ist, als die Umgebung erlaubt; der Gerätedialog warnt schon beim Tippen des Namens. **Doppelt** markiert einen Namen, den eine andere Variable der Maschine auch hat, egal in welcher Groß- oder Kleinschreibung. **Keine Adresse** markiert ein Signal ohne SPS-Adresse, **Eigener Name** eine Variable, deren Namen du selbst gesetzt hast. Keiner dieser Hinweise hält dich auf; sie zeigen, was noch offen ist.

## Variablen korrigieren und ergänzen

Bearbeite eine gebildete Variable, um ihr einen eigenen Namen zu geben. Der Name wird am Signal des Geräts gespeichert, wandert also mit dem Gerät mit, und die Liste hält nie eine Kopie, die abweichen könnte. **Gebildeten Namen verwenden** geht zum gebildeten Namen zurück. **Variable hinzufügen** ergänzt eine Variable, die zu keinem Gerät gehört, etwa eine HMI-Taste oder ein Signal vom Roboter, mit Typ, Adresse und Kommentar. Ein Variablenname enthält nur Buchstaben, Ziffern und Unterstriche.

## Export

**Exportieren** schreibt die Liste als Excel-Datei in den Spalten der Umgebung, auf das Tabellenblatt, das sie nennt, fertig für den Import der SPS-Software. Sicherheitssignale kommen in die Variablentabelle für Sicherheitssignale, wenn die Umgebung eine hat.

## Beispiele

**Ein Sensor eines Zylinders.** B01 Hubzylinder P1 hat einen Eingang, der Ausgefahren bestätigt, mit dem SPS-Zustand Ausgefahren. Seine Variable ist di_B01_Hubzylinder_P1_Ausgefahren.

**Ein Umlaut im Namen.** Die Umgebung wandelt ü in ue um, derselbe Eingang an B03 Drücker P1 wird also zu di_B03_Druecker_P1_Ausgefahren.

**Ein Not-Halt mit zwei Kanälen.** Beide Eingänge von B00 Taster Not-Halt bestätigen Gedrückt, beide werden also zu fdi_B00_Taster_Not_Halt_Gedrueckt und sind als **Doppelt** markiert. Gib ihnen die Variablenendungen Kanal1 und Kanal2, und die Hinweise verschwinden.

**Ein Robotersignal.** **Variable hinzufügen** mit dem Namen di_Roboter_Bereit, Typ DI und Adresse I3.0 nimmt das Bereitsignal des Roboters in den Export auf.
