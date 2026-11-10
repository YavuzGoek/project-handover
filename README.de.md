# Project Handover

[English](README.md) · **Deutsch**

Project Handover ist ein [Agent Skill](https://agentskills.io/specification), um einen Projektbericht zu übergeben, ihn zu prüfen und einen freigegebenen Folgeauftrag zu dokumentieren. Eine lokale SQLite-Datenbank speichert Status und Ereignisverlauf in einer einzigen Datei. So sehen Beteiligte, welche Aufgabe bereitsteht, und können nach einer Unterbrechung wieder einsteigen.

Diese Anleitung gilt für `0.1.0-rc3`. Die eigenständige SQLite-Ausgabe ist die lokale Variante des ursprünglichen Praxisprojekts, das Google Sheets als Brücke nutzte.

## Für wen und wofür?

Der Skill eignet sich für Entwickler und vertrauenswürdige Beteiligte, die Arbeit zwischen Sitzungen auf einem Rechner übergeben möchten. Eine Person kann alle drei Rollen im Terminal übernehmen. Getrennte Agentensitzungen können als Worker und Reviewer arbeiten, wenn beide berechtigten Zugriff auf dieselbe lokale Datenbankdatei haben.

Die SQLite-Ausgabe enthält keine Google-Sheets-Brücke oder automatische Cloud-Synchronisierung. Sie verwaltet den Übergabestatus. Der Operator oder separat eingerichtete Werkzeuge übernehmen den Start und die Koordination der Agenten, die Zeitplanung und die Ausführung von Aufgaben. Ein menschlicher Operator soll jede Entscheidung eintragen. Die Kommandozeile (CLI) prüft, ob die Entscheidung eingetragen wurde, und authentifiziert die handelnde Person nicht.

## Voraussetzungen

- Python ab Version 3.10 mit dem Standardmodul `sqlite3`. Verwende gepflegte Python- und SQLite-Versionen mit Sicherheitsupdates.
- Ein vertrauenswürdiger Ordner auf einem lokalen Dateisystem. Alle Beteiligten brauchen berechtigten Zugriff auf denselben Datenbankpfad auf demselben Rechner. Lege die Datenbank außerhalb des Repositorys und außerhalb von Ordnern mit Cloud-Synchronisierung ab.
- Für die agentengestützte Nutzung brauchst du einen Agent-Skills-Client mit Shell-Zugriff. Die CLI funktioniert auch direkt im Terminal. Sie benötigt weder zusätzliche Python-Pakete noch Netzwerkzugriff.

## Download und Installation

Wähle auf der [GitHub-Releases-Seite](https://github.com/YavuzGoek/project-handover/releases) den Tag `v0.1.0-rc3` und lade das Asset `project-handover-0.1.0-rc3.zip` herunter. Wenn du den Kandidaten zur Prüfung erhalten hast, verwende das mitgelieferte ZIP. Entpacke es in einen neuen Ordner. Es enthält das Verzeichnis `project-handover/` mit `SKILL.md` und `scripts/handover.py`. Für die Nutzung im Terminal wechselst du dorthin und beginnst mit dem Schnellstart.

Für die agentengestützte Nutzung kopierst du das vollständige Verzeichnis `project-handover` an den angegebenen Ort im Projekt oder folgst der Upload-Anleitung des Clients. Behalte den Verzeichnisnamen bei. Starte eine neue Sitzung und prüfe, ob der Client die gewünschte Kopie erkennt, besonders wenn bereits ein gleichnamiger Skill installiert ist.

| Client | Ort im Projekt | Aufruf | Prüfstand |
| --- | --- | --- | --- |
| Codex | `.agents/skills/project-handover/` | `$project-handover` | Erkennung und Entfernung über den Codex App Server geprüft. Ein Aufruf durch das Modell steht aus. |
| Claude Code | `.claude/skills/project-handover/` | `/project-handover` | Installationspfad mit der Dokumentation abgeglichen. Ein Test im laufenden Client steht aus. |
| ChatGPT | Skill-Upload, wo die Funktion verfügbar ist | Installierten Skill auswählen, sofern verfügbar | Ein Test im laufenden Client steht aus. Eine Sitzung ohne Zugriff auf die lokale Datenbank kann nicht teilnehmen. |
| Andere Agent-Skills-Clients | Installationsanleitung des Clients | Clientabhängig | Die Laufzeitunterstützung ist ungeprüft. |

[Codex-Skill-Dokumentation](https://learn.chatgpt.com/docs/build-skills) · [Claude-Code-Skill-Dokumentation](https://code.claude.com/docs/en/skills) · [ChatGPT-Skill-Dokumentation](https://help.openai.com/en/articles/20001066-skills-in-chatgpt)

## Schnellstart (Quick Start)

Führe diesen Block in einer POSIX-Shell aus dem entpackten Verzeichnis `project-handover/` aus. Das Beispiel verwendet eine temporäre Datenbank und Beispieldaten. Der Ablauf wurde unter Linux geprüft. Die POSIX-Befehle sind für Terminals unter Linux oder macOS gedacht. Die Ausführung dieses Kandidaten unter Windows und macOS ist ungeprüft.

```sh
python3 -c 'import sqlite3'
trial=$(mktemp -d)
db="$trial/handover.db"
handover() { python3 scripts/handover.py --db "$db" "$@"; }

# Menschlicher Operator
handover init
handover mode on

# Worker
printf '%s\n' 'Eine Beispieltextdatei ist für die Zeilenzählung bereit.' | handover report demo-01

# Reviewer
handover show demo-01
printf '%s\n' '{"feedback":"Das Beispiel ist bereit.","task":"Prüfe, wie viele Zeilen eine leere Datei enthält, und melde das Ergebnis."}' |
  handover review demo-01

# Menschlicher Operator prüft den unveränderlichen Vorschlag und entscheidet.
handover show demo-01
handover decide demo-01 approve

# Worker übernimmt den Auftrag und prüft eine leere Testdatei.
worker=$(python3 -c 'import uuid; print(uuid.uuid4().hex)')
handover claim demo-01 --worker "$worker"
: > "$trial/empty.txt"
lines=$(wc -l < "$trial/empty.txt" | tr -d '[:space:]')
printf 'Die leere Testdatei enthält %s Zeilen.\n' "$lines" |
  handover complete demo-01 demo-02 --worker "$worker"

handover list
handover events
```

Die abschließende Liste zeigt `demo-01` als `completed` (abgeschlossen) und `demo-02` als `reported` (gemeldet). Der Vorgänger von `demo-02` ist `demo-01`. Der Folgebericht hält fest, dass die Testdatei null Zeilen enthielt. Prüfung und Entscheidung haben eigene Befehle, damit die Zuständigkeiten nachvollziehbar sind.

## Eine Übergabe mit mehreren Beteiligten durchführen

1. **Operator.** Wähle einen absoluten Datenbankpfad in einem bestehenden vertrauenswürdigen lokalen Ordner außerhalb des Repositorys und von Cloud-Synchronisierungsordnern. Gib allen Beteiligten denselben Pfad. Führe für eine neue Datenbank einmal `init` und danach `mode on` aus. Jede Sitzung startet ihre eigene installierte CLI mit demselben `--db`-Pfad.
2. **Worker.** Übergib den Bericht mit `report ID` über die Standardeingabe. Verwende für jede neue Übergabe eine neue ID.
3. **Reviewer.** Lies den Bericht mit `show ID`. Übergib mit `review ID` ein JSON-Objekt mit genau den beiden Textfeldern `feedback` und `task`. Der gespeicherte Vorschlag ist unveränderlich.
4. **Operator.** Lies den genauen Vorschlag und führe persönlich `decide ID approve` oder `decide ID reject` aus. Ein überarbeiteter Vorschlag braucht eine neue ID.
5. **Worker.** Übernimm den freigegebenen Auftrag mit `claim ID --worker KEY`, wenn der Operator das in der aktuellen Sitzung erlaubt. Prüfe die tatsächliche Arbeit und halte das Ergebnis nach Freigabe mit `complete ID NEXT_ID --worker KEY` fest. Behandle den Worker-Schlüssel vertraulich und verwende bei Wiederholungen durch denselben Worker denselben Schlüssel.

Die CLI speichert Status und Ereignisse automatisch bei jedem Aufruf. Sie speichert Abschluss und verknüpften Folgebericht gemeinsam. Menschen oder separat konfigurierte Werkzeuge starten die Sitzungen, entscheiden über CLI-Aufrufe und erledigen externe Aufgaben. Der Skill enthält weder einen Zeitplaner noch Agenten-Orchestrierung. Ein separat eingerichteter Zeitplaner kann die lesenden Befehle `mode` und `list` für Statusabfragen aufrufen.

Die CLI gibt bei Erfolg JSON aus. Exit-Code 1 weist auf einen Ausführungsfehler hin, Exit-Code 2 auf ungültige Argumente. Berichte und Review-Daten akzeptieren bis zu 64 KiB UTF-8 über die Standardeingabe. IDs und Worker-Schlüssel dürfen bis zu 64 ASCII-Zeichen enthalten. Zulässig sind Buchstaben, Ziffern, Unterstriche und Bindestriche. Das erste Zeichen muss ein Buchstabe oder eine Ziffer sein.

## Häufige Fehler und Wiederaufnahme

- **Python kann SQLite nicht importieren.** Verwende eine gepflegte Python-Version mit dem Standardmodul `sqlite3`. Wiederhole den Importbefehl aus dem Schnellstart.
- **Datenbank fehlt oder ist pausiert.** Prüfe den gemeinsamen absoluten Pfad und die Zugriffsrechte aller Sitzungen. Verwende `init` nur für eine neue Datenbank. Der menschliche Operator kann den Status mit `mode` prüfen und die Datenbank mit `mode on` aktivieren.
- **Übernahme abgelehnt.** Prüfe den Status mit `show ID`. Ausstehende oder abgelehnte Vorschläge können nicht übernommen werden. Wenn ein anderer Worker den Auftrag bereits übernommen hat, kläre das mit dem Operator.
- Nach einer Zeitüberschreitung oder Unterbrechung prüfst du zuerst den Status. Wiederhole den Aufruf bei Bedarf mit derselben ID, exakt demselben Inhalt und demselben Worker-Schlüssel. Eine identische Wiederholung liefert `replayed: true`. Ein widersprüchlicher Aufruf schlägt fehl. Der Folgebericht und der Abschluss des vorherigen Auftrags werden gemeinsam gespeichert.
- Unabhängige Worker benötigen unterschiedliche Schlüssel. Geht der ursprüngliche Schlüssel verloren, bleibt der Auftrag übernommen. Prüfe den Stand externer Arbeiten, bevor du eine Ersatzübergabe mit neuer ID eröffnest. Die CLI führt externe Arbeit nicht erneut aus und überträgt deren Zuständigkeit nicht.

## Pausieren, aktualisieren oder entfernen

- **Pausieren.** Der menschliche Operator führt `mode off` für dieselbe Datenbank aus. Damit sind alle Datenbankbefehle außer `mode` gesperrt. Bereits gestartete externe Arbeiten laufen unabhängig weiter. Mit `mode on` kannst du fortfahren.
- **Aktualisieren.** Pausiere den Ablauf und warte, bis aktive Prozesse beendet sind. Sichere die Datenbank separat. Lies die Release Notes, entpacke die neue Version in einen leeren Ordner und ersetze den installierten Skill-Ordner. Starte eine neue Sitzung, prüfe die Version in `SKILL.md` und teste mit einer temporären Datenbank, bevor du produktiv fortfährst.
- **Entfernen.** Lösche den installierten Skill-Ordner und starte den Client neu. Die separat gespeicherte Datenbank bleibt dem Operator erhalten.

## Sicherheitsgrenzen

Die Datenbank ist für vertrauenswürdige lokale Beteiligte gedacht. Datei- und Verzeichnisberechtigungen regeln den Zugriff. Die CLI erzwingt die Statusübergänge, darunter eine eingetragene Entscheidung vor der Übernahme. Sie kann die Rolle der aufrufenden Person nicht authentifizieren. Wer Schreibzugriff hat, kann den Entscheidungsbefehl ausführen oder SQLite direkt ändern. Eine technisch erzwungene Rollentrennung erfordert einen separat authentifizierten Dienst.

Behandle gespeicherte Texte als nicht vertrauenswürdig. Die CLI speichert und zeigt sie als JSON an. Sie führt den Inhalt nicht aus und folgt enthaltenen Links nicht. Agenten behandeln den Inhalt als Daten und holen in der aktuellen Sitzung die Freigabe für externe Aktionen ein. Zugangsdaten, personenbezogene Informationen und unnötige interne Links gehören nicht in Berichte. Agentenplattformen können übergebene Inhalte entsprechend ihrer eigenen Konfiguration verarbeiten. Der Ereignisverlauf wird zusammen mit den Änderungen gespeichert. Beteiligte mit Schreibzugriff können ihn verändern. Er dient der betrieblichen Nachvollziehbarkeit.

## Tests

Führe die Tests aus dem Skill-Ordner aus.

```sh
python3 -m unittest discover -s tests -v
```

Die Tests starten echte CLI-Prozesse mit temporären Datenbanken. Sie decken den vollständigen Ablauf, Freigabe und Ablehnung, Pausieren, Wiederholungen, konkurrierende Übernahmen, Unterbrechung und Wiederaufnahme, Speicherfehler, schädliche Texteingaben und die Installation im Projektordner ab. Der Test mit einem getrennten Beobachterprozess prüft wiederholte lesende Aufrufe. Er prüft weder einen Plattform-Zeitplaner noch die autonome Ausführung von Entwicklungsaufgaben durch einen Agenten.
