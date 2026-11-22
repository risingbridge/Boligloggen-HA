# Huslogg – applikasjonsplan (utkast v0.1)

*Delt vedlikehold for husstanden – med årshjul, skreddersydd plan og varsler.*

---

## 1. Posisjonering

Huslogg er en app for å holde oversikt over nødvendig og anbefalt vedlikehold av bolig og fritidseiendom. Kjernen er enkel: tilbakevendende gjøremål delt på type og hyppighet, visualisert i et årshjul, som flere i husstanden kan dele og oppdatere sammen.

**Det vi skal være best på (differensiatorer):**
- Delt vedlikehold mellom flere likeverdige brukere på samme eiendom (begge i et forhold, hele familien).
- Skreddersydd vedlikeholdsplan basert på den faktiske boligen, ikke en generisk sjekkliste.
- Lavterskel-forklaringer skrevet for folk uten fagkunnskap.
- Årshjulet som visuell signatur.

**Det vi ikke prøver å bli:** en altomfattende dokumentasjons-/eiendomsplattform (det gjør Boligmappa og Eigar allerede). Vi kan heller integrere mot dem senere.

---

## 2. Roller og tilgang

To roller per eiendom:

| Handling | Eier | Medlem |
|---|---|---|
| Se gjøremål, årshjul og logg | ✓ | ✓ |
| Fullføre og dokumentere gjøremål | ✓ | ✓ |
| Legge til egne gjøremål på eiendommen | ✓ | – |
| Fjerne gjøremål som ikke gjelder eiendommen | ✓ | – |
| Endre eiendomsdetaljer / vedlikeholdsplan | ✓ | – |
| Invitere og fjerne brukere | ✓ | – |
| Overføre eierskap (og «vaske» logg) | ✓ | – |
| Slette eiendom | ✓ | – |

En eiendom kan ha flere eiere (f.eks. et par som eier sammen). Minst én eier må alltid finnes. Medlemmer fullfører og dokumenterer gjøremål, men det er eier som forvalter selve vedlikeholdsplanen.

---

## 3. Onboarding og skreddersydd vedlikeholdsplan

Dette er den viktigste funksjonen å få riktig – det er her vi skiller oss fra en statisk kalender. Onboardingen samler inn noen få, enkle svar og genererer en startplan brukeren kan justere.

**Innsamlede data:**
- Adresse (gir geografi/klima – kyst vs. innland, snølast, nedbør)
- Boligtype (enebolig, rekkehus, leilighet, hytte)
- Byggeår / alder
- Oppvarming (vedovn/pipe, varmepumpe, radiatorer, gulvvarme, elektrisk)
- Ventilasjon (balansert med filter, avtrekk, naturlig)
- Utvendig kledning (trevirke/maling, mur, annet)
- Vannforsyning (offentlig vs. egen brønn)
- Antall bad/våtrom
- Uteareal (hage, terrasse, carport/garasje)

**Hvordan svarene former planen (eksempler):**
- *Leilighet* → fjerner husvask, takrenner, drenering; beholder bad/sluk/ventilasjon.
- *Hytte* → legger til frostsikring, stenge/åpne vann, sesongåpning/-stenging.
- *Eldre bolig (f.eks. >30 år)* → foreslår el-kontroll, sjekk av drenering, vurdering av varmtvannsbereder.
- *Vedovn/pipe* → feiing og sjekk av ildsted.
- *Varmepumpe* → rens/bytte filter, utvendig enhet.
- *Egen brønn* → vannprøve/brønnsjekk.
- *Trekledning* → maling/beis med klimajustert intervall (oftere langs kysten).

Hver oppgave i katalogen har betingelser for når den skal inkluderes, en standard hyppighet, og eventuelt en fast dato (f.eks. røykvarsler 1. desember). Brukeren kan alltid legge til, fjerne eller justere oppgaver etterpå.

**Flyt:** onboardingen genererer en ferdig vedlikeholdsplan som *første* steg. I *neste* steg får eier en gjennomgang der hun kan justere – fjerne det som ikke passer, legge til særegenheter, endre hyppighet. De samme endringene kan gjøres når som helst senere. Brukeren starter altså aldri med blanke ark, men beholder full kontroll.

---

## 4. Vedlikeholdsmodellen

- **Eierskap til oppgaver:** gjøremål tilhører *eiendommen*, ikke en bestemt person. Hvem som helst i husstanden kan fullføre dem, og loggen fanger opp hvem som faktisk utførte den enkelte gangen.
- **Tilpasning:** eier kan legge til egendefinerte gjøremål for boligens særegenheter (f.eks. et spesielt anlegg eller en gammel pipe), og fjerne forhåndsutfylte punkter som ikke gjelder akkurat denne eiendommen.
- **Hyppighet:** månedlig, kvartalsvis, halvårlig, årlig (og mulighet for «hvert N. år» for ting som maling).
- **To planleggingstyper:** *intervall* (regnes fra forrige utførte gang) og *fast dato* (faller på samme dag hvert år).
- **Årshjul:** viser når oppgaver faller gjennom året, fargekodet etter hyppighet; månedlige rutiner vises som egen note.
- **Logg:** hver fullføring lagres med dato, hvem som utførte den, notat og evt. bilde.

---

## 5. Varsler

**Push (må-ha fra start):**
- Gjøremål forfaller snart (konfigurerbart, f.eks. 3 dager før).
- Gjøremål på overtid.
- Et medlem fullførte en oppgave («Ola fullførte ‘rense sluk’») – gir den delte husstandsfølelsen.
- Sesong-/værbaserte tips senere (frost meldt, storm i helgen).

**Kalender-sync:**
- MVP: en skrivebeskyttet ICS-abonnementsfeed per eiendom som brukeren kan koble til Google/Apple/Outlook. Enkelt å bygge, lav risiko.
- Senere: toveis-sync, slik at å huke av i kalenderen markerer oppgaven som utført.

**Varselinnstillinger:** per bruker (ikke per eiendom), så hver i husstanden styrer sine egne varsler.

---

## 6. Eierskifte (overføring ved salg)

1. Eier starter en overføring og oppgir ny eiers e-post.
2. Ny bruker får invitasjon og bekrefter (gjerne med identifisering).
3. Eierskap flyttes; den opprinnelige eieren kan velge å forlate eller bli værende som medlem.

**Beslutning – historikk ved overføring:** vedlikeholdsloggen følger eiendommen videre, fordi den er verdifull dokumentasjon for ny eier. Men avtroppende eier kan «vaske» loggen først – fjerne personlige notater og bilder – før overføringen fullføres. Selve hendelseshistorikken (hvilke gjøremål som ble gjort når) beholdes.

---

## 7. Datamodell (skjematisk)

- **User** – id, navn, e-post, varslingsinnstillinger
- **Property** – id, adresse, matrikkelinfo, type, byggeår, attributter (oppvarming, ventilasjon, kledning …)
- **Membership** – user_id, property_id, rolle (eier/medlem), status
- **TaskTemplate** (katalog) – tittel, beskrivelse, kategori, standard hyppighet, inkluderingsbetingelser, evt. fast dato
- **Task** (instans på en eiendom) – property_id, template_id eller egendefinert, hyppighet, neste forfall, status
- **LogEntry** – task_id, utført_av (user_id), dato, notat, bilde
- **Invitation** – property_id, e-post, rolle, token, status
- **TransferRequest** – property_id, fra_bruker, til_bruker/e-post, status

Sentral relasjon: en bruker kan ha mange eiendommer, og en eiendom kan ha mange brukere – koblet via Membership med rolle.

---

## 8. Tekniske valg og mulige integrasjoner

- **Vær/klima:** met.no (Yr) sitt åpne API for sesong-/værvarsler og klimajustering av planen ut fra adresse.
- **Eiendomsdata:** mulig oppslag mot matrikkel for å forhåndsutfylle boligtype/byggeår i onboardingen.
- **Boligmappa:** valgfri integrasjon senere – les eiendomsdata, skriv tilbake utført vedlikehold som dokumentasjon, slik at brukeren slipper dobbeltføring.
- **Kalender:** ICS-feed (MVP), CalDAV/Google/Microsoft Graph (senere).
- **Push:** standard mobil push (APNs/FCM).

---

## 9. Personvern og sikkerhet

- Delte data betyr tydelig tilgangsstyring: en bruker skal kun se eiendommer de er medlem av.
- Personlige notater og bilder i loggen må håndteres bevisst ved eierskifte.
- Identifisering skjer med e-post i første omgang (gjerne magisk lenke eller Google/Apple-innlogging). BankID blir først aktuelt hvis appen skal koble til Boligmappa (som krever det) eller hente persontilknyttede offentlige data – da trengs sterkere identifisering.
- GDPR: eksport og sletting av egne data.

---

## 10. Faseplan

**MVP (v0.1)**
- Flere eiendommer per bruker
- Mal-/manuelt baserte gjøremål, hyppighet og fast dato
- Årshjul, logg, fullføring med dokumentasjon
- Roller (eier/medlem), invitasjon
- Push for forfall og overtid
- Enkel onboarding (et lite sett spørsmål)

**v1**
- Skreddersydd vedlikeholdsplan generert fra full onboarding
- Kalender-sync (ICS)
- Eierskifte-flyt
- Sesong-/værvarsler (met.no)

**v2**
- Vedlikeholdsøkonomi og komponentlevetid (forutse storutgifter)
- Steg-for-steg-guider med video
- Håndverkerkobling
- Boligmappa-integrasjon, hytte-spesifikke moduler

---

## 11. Åpne spørsmål

- Skal egendefinerte gjøremål kunne foreslås tilbake til malkatalogen (så gode forslag kommer andre til gode), eller holdes de helt private per eiendom?

### Avklart så langt
- Gjøremål tildeles eiendom, ikke person, og er åpne for hele husstanden; loggen fanger hvem som utførte.
- Eier forvalter planen (legge til egne / fjerne ugyldige gjøremål); medlemmer fullfører og dokumenterer.
- Logg følger eiendommen ved salg, men eier kan «vaske» personlige notater/bilder først.
- To roller: eier og medlem.
- Identifisering med e-post i første omgang; BankID først hvis vi kobler til Boligmappa eller henter persontilknyttede offentlige data.
- Onboarding genererer planen automatisk som steg 1, deretter et redigeringssteg der eier justerer (og kan endre når som helst senere).
