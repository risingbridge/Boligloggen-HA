# Huslogg – onboarding og spørsmålssett (MVP)

*Følgedokument til `huslogg-applikasjonsplan.md` og `huslogg-webapi-mvp.md`. Beskriver onboarding-flyten og selve spørsmålssettet som setter opp eiendommen og et startsett gjøremål. Utkast v0.1.*

---

## 0. Mål og prinsipper

Onboardingen skal sette opp riktig eiendom og et fornuftig startsett gjøremål på **under to minutter for en typisk bolig**, uten at brukeren opplever et langt skjema. Den er den viktigste funksjonen for å skille oss fra en statisk sjekkliste (planen §3), men den må ikke koste brukeren mer enn den gir.

Fire prinsipper styrer settet:

- **Boligtype først.** Ett svar tidlig beskjærer resten av treet – en leilighetseier skal aldri se spørsmål om takrenner eller oppkjørsel.
- **Spør bare om det som endrer planen.** Hvert spørsmål må kunne knyttes til minst én oppgave det inkluderer, ekskluderer eller justerer. Gir det ikke utslag i planen, hører det ikke hjemme i onboardingen.
- **Utled og default framfor å spørre.** Klima/kyst utledes av adressen; usikre svar («vet ikke») defaultes etter byggeår. Alt kan rettes senere.
- **To-stegs flyt.** Onboardingen *genererer* planen som steg 1, deretter justerer eier i et redigeringssteg (planen §3, MVP §6). Fordi steg 2 fanger opp resten, trenger spørsmålene bare treffe grovt – det tillater et kort sett.

Antall spørsmål styres av de første svarene, ikke av et fast skjema: ~12 for enebolig, ~6 for leilighet, litt flere for hytte. Nesten alle er ett-trykks kort/chips.

---

## 1. Blokkstruktur og betinget logikk

Spørsmålene er delt i fire blokker. Blokk A vises alltid; B–D vises betinget av boligtype og av enkelte ja/nei-svar som fungerer som gruppefiltre (f.eks. «hage: nei» skjuler en hel gruppe).

```
A. Grunnlag        → alle
B. Bygningen       → enebolig, rekkehus, hytte (i stor grad skjult for leilighet)
C. Uteområde       → enebolig, rekkehus, hytte (skjult for leilighet)
D. Hytte-spesifikt → kun hytte
```

Rekkehus/tomannsbolig behandles som enebolig, med uteblokken vist på lik linje – hvert element gates individuelt med ja/nei (§4), som fanger at rekkehus ofte har begrenset eller delt uteareal.

---

## 2. Blokk A – Grunnlag (alle)

| Spørsmål | Svaralternativer | Hva det avgjør |
|---|---|---|
| **Adresse** | Adressesøk med autofullfør | Geografi/klima (kyst vs. innland, nedbør, snølast) → klimajustering av intervaller (v1), grunnlag for senere matrikkel-prefill og vær-varsler. |
| **Boligtype** | Enebolig · Rekkehus/tomannsbolig · Leilighet · Hytte | **Hovedfilteret.** Bestemmer hvilke blokker som vises og hvilke maler som er relevante. |
| **Byggeår** | Årstall, eller bånd ved «vet ikke»: <10 / 10–30 / 30–50 / >50 år | Aldersbaserte oppgaver: el-kontroll, sjekk av drenering, vurdering av rør/bereder, vindussjekk. Nyere bolig → færre tilstandsoppgaver. |

---

## 3. Blokk B – Bygningen (skjules i stor grad for leilighet)

| Spørsmål | Svaralternativer | Hva det avgjør |
|---|---|---|
| **Oppvarming** (flervalg) | Vedovn/peis m/pipe · Varmepumpe · Vannbåren (radiator/gulvvarme) · Elektrisk · Fjernvarme | Vedovn → feiing + sjekk av ildsted. Varmepumpe → filterrens + spyl utedel + kondensavløp. Vannbåren → lufting + fordelerskap/trykk. Elektrisk/fjernvarme → lite ekstra. |
| **Ventilasjon** | Balansert m/varmegjenvinning · Mekanisk avtrekk · Naturlig · Vet ikke | Balansert → filterbytte 1–2×/år (den mest glemte oppgaven). Avtrekk → rens vifte/ventiler. Naturlig → sjekk ventiler. «Vet ikke» defaulter etter byggeår. |
| **Utvendig kledning** | Tre (malt/beiset) · Mur/puss · Tegl · Kombinasjon | Tre → maling/beis med klimajustert intervall. Mur/puss → sjekk av puss/fuger. Tegl → lite. Skjules for leilighet. |
| **Antall bad/våtrom** | 1 · 2 · 3+ | Skalerer rens av sluk og sjekk av fuger/silikon/membran per våtrom. |

---

## 4. Blokk C – Uteområde (skjules for leilighet)

**Hvert element gates individuelt med ja/nei (eller «Ingen»).** I stedet for én «hopp over hele blokken»-knapp svarer brukeren separat på hage, oppkjørsel, platting, garasje og vann. Den som ikke har noe eget uteareal trykker bare «Nei/Ingen» nedover lista – like raskt som å hoppe over, men mer presist. Der et svar utløser et oppfølgingsspørsmål (har oppkjørsel → hvilket underlag?), vises underspørsmålet først når man har svart ja.

**Dette løser rekkehus rent.** Rekkehus/tomannsbolig er et ekte mellomtilfelle: leilighet har så godt som aldri eget uteareal (blokken skjules), enebolig har det nesten alltid (blokken vises), men rekkehus er blandet – noen har egen hageflekk, platting og inngangsoppkjørsel, andre har fellesarealer et sameie steller, eller ingenting eget. Per-element-gating fanger nettopp denne miksen: en rekkehuseier kan ha egen hage, men si nei til oppkjørsel og garasje. Vi viser altså blokken for rekkehus på lik linje med enebolig, og lar ja/nei-svarene forme planen. Ingen særbehandling av boligtypen trengs.

| Spørsmål | Svaralternativer | Hva det avgjør |
|---|---|---|
| **Egen hage/plen?** | Ja · Nei | Ja → sesongoppgaver (løvraking, takrennerens om høsten, plenpleie). |
| **Egen oppkjørsel?** | Nei · Asfalt · Belegningsstein · Grus · Betong | Asfalt → tett sprekker (mot frostsprengning). Belegningsstein → ugress i fuger + ettersanding/fugesand + retting av setninger. Grus → etterfylling/planering. Betong → sjekk sprekker/fuger. |
| **Terrasse/platting?** | Nei · Tre · Kompositt/stein | Tre → rens + olje/beis årlig. Kompositt/stein → kun rens. |
| **Garasje/carport?** | Nei · Garasje m/port · Carport | Port → smøring/sjekk av mekanisme + fotocelle. Eget tak/renner å vedlikeholde. |
| **Vannforsyning** | Offentlig · Egen brønn/borehull | Egen brønn → vannprøve (bakterier) + brønn/pumpe-sjekk. Offentlig → ingenting ekstra. |

---

## 5. Blokk D – Kun hytte

| Spørsmål | Svaralternativer | Hva det avgjør |
|---|---|---|
| **Vinterbruk** | Vinterstengt/uoppvarmet · Helårs | Vinterstengt → frostsikring, stenge/tømme vann om høsten, åpne/fylle om våren, sesong-stell. |
| **Vann på hytta** | Innlagt helår · Sommervann · Ikke innlagt | Om vann-relaterte oppgaver i det hele tatt gjelder. |

Hytte arver også relevante spørsmål fra blokk B/C (oppvarming, kledning, terrasse) der de gir mening.

---

## 6. Hva vi bevisst *ikke* spør om

Å utelate er like viktig som å inkludere. Følgende holdes ute av onboardingen:

- **Kvadratmeter og antall rom** – påvirker ikke hvilke oppgaver som gjelder, bare (eventuelt) mengde. Ikke verdt et spørsmål.
- **Alder på enkeltkomponenter** (bereder, tak, vinduer) – hører til v2 (vedlikeholdsøkonomi/komponentlevetid), ikke MVP-onboarding.
- **Lovpålagte/tekniske detaljer brukeren ikke kan svare på** – gir «vet ikke» og friksjon uten gevinst.
- **Alt som kan utledes:** klima/kyst fra adresse; takrenner/drenering fra boligtype + hage; ventilasjonsdefault fra byggeår.

---

## 7. Kobling mot datamodell (`PropertyAttributes`)

Spørsmålene mapper til `PropertyAttributes` (MVP §4.1). Dagens MVP-modell dekker det meste, men **oppkjørsel, terrasse og ventilasjon mangler felt**. Disse legges til i MVP-en (avklart – se under), siden spørsmålene ellers ikke ville gitt utslag:

```csharp
public sealed class PropertyAttributes
{
    public HeatingType[] Heating { get; set; } = [];
    public VentilationType Ventilation { get; set; }       // (utvid MVP: mangler i dag)
    public CladdingType Cladding { get; set; }
    public WaterSupply Water { get; set; }                 // Public | OwnWell
    public int BathroomCount { get; set; }
    public OutdoorFeature[] Outdoor { get; set; } = [];    // Hage, Garasje, Carport …
    public DrivewaySurface Driveway { get; set; }          // NY: None|Asphalt|Pavers|Gravel|Concrete
    public DeckType Deck { get; set; }                     // NY: None|Wood|CompositeOrStone
    public CabinWinterUse? CabinWinterUse { get; set; }    // NY: kun hytte
}
```

**Avklart:** attributt-drevet inkludering tas inn samtidig med at disse feltene legges til – ikke utsatt til v1. Grunnen er enkel: uten den gir oppkjørsel- og ventilasjonsspørsmålene ingen utslag, og da er det ingen vits i å stille dem. Ren `ForTypes`-filtrering (boligtype) klarer ikke å skille asfalt fra belegningsstein.

Konkret betyr det at MVP-seedingen bruker **begge** nivåer: `TaskTemplate.ForTypes` for det grove boligtype-kuttet, og et lite sett attributt-betingelser fra den `InclusionRule`-modellen som allerede finnes i full-designet (design §6.1). For MVP trengs bare betingelsene som de nye spørsmålene faktisk krever:

```csharp
public sealed class InclusionRule
{
    public PropertyType[]? ForTypes { get; set; }              // grovt kutt (som før)
    public HeatingType[]? RequiresAnyHeating { get; set; }     // vedovn → feiing, varmepumpe → filter
    public VentilationType[]? RequiresVentilation { get; set; }// balansert → filterbytte
    public CladdingType[]? RequiresCladding { get; set; }      // tre → maling
    public bool? RequiresOwnWell { get; set; }                 // egen brønn → vannprøve
    public DrivewaySurface[]? RequiresDriveway { get; set; }   // asfalt vs. belegningsstein
    public DeckType[]? RequiresDeck { get; set; }              // tre → olje/beis
    public int? MinAgeYears { get; set; }                      // eldre bolig → el-kontroll
}
```

`OnboardingService.SeedTasks` (MVP §6) bytter da ut det rene `ForTypes`-predikatet med `Where(t => t.Inclusion.Matches(property, clock.Today))`. Dette er en avgrenset utvidelse – ikke full v1-plangenerering (ingen klimajustering, ingen met.no) – men det gjør at hvert onboarding-spørsmål faktisk får konsekvens i planen. Klimajustering av *intervaller* forblir v1.

---

## 8. Flyt og API

Uendret fra MVP §6 – onboardingen skriver til de eksisterende endepunktene:

1. **`POST /api/onboarding`** tar imot svarene, oppretter `Property` med `AppUser` som eier via `Membership`, og seeder `MaintenanceTask`-instanser fra malkatalogen (kopiert fra maler, så senere katalogendringer ikke overskriver planen). Returnerer forslaget.
2. Eier justerer i redigeringssteget via de vanlige task-endepunktene (`POST/PATCH/DELETE .../tasks`). Ingen egen «onboarding-modus» i datamodellen.

Request-formen speiler blokkene, med attributtene samlet i ett objekt:

```jsonc
POST /api/onboarding
{
  "address": "Eksempelveien 1, 7000 Trondheim",
  "type": "Enebolig",
  "buildYear": 1985,
  "attributes": {
    "heating": ["WoodStove", "HeatPump"],
    "ventilation": "Natural",
    "cladding": "Wood",
    "water": "Public",
    "bathroomCount": 2,
    "outdoor": ["Garden", "Garage"],
    "driveway": "Pavers",
    "deck": "Wood"
  }
}
```

**Skjemaet ligger klientside i MVP-en** (avklart). Klienten eier spørsmålsrekkefølge, alternativer og betinget visning; APIet tar bare imot det ferdige svaret over `POST /api/onboarding`. Det er raskest å bygge, og siden vi uansett vil bruke MVP-en til å prøve ut ulike spørsmålssett (§10), er det en fordel at endringer skjer i klienten uten å versjonere et API-skjema. Baksiden – at nye spørsmål krever klientutrulling – er akseptabel så lenge vi eksperimenterer.

Kontrakten mot APIet er likevel verdt å holde stabil: `attributes`-objektet er det som persisteres og driver seeding, så nye spørsmål bør legge til felt der framfor å endre formen på eksisterende. Da kan et server-levert skjema (`GET /api/onboarding/schema`) innføres senere uten å røre onboarding-endepunktet – speiler valget om å legge årshjul-projeksjonen server-side (MVP §8), men trekkes altså motsatt vei her fordi skjemaet endrer seg oftere enn det trenger å være konsistent på tvers av plattformer.

---

## 9. Estimert lengde

| Boligtype | Antall spørsmål | Anslått tid |
|---|---|---|
| Leilighet | ~6 (A + oppvarming/ventilasjon/bad) | < 1 min |
| Enebolig / rekkehus | ~12 | ~2 min |
| Hytte | ~13 | ~2 min |

Uteblokken svares element for element med ja/nei – den som ikke har eget uteareal trykker raskt «Nei/Ingen» nedover og er straks videre, mens den som har det får hvert relevante element med. Ingen mister noe: også det som svares nei på kan legges til i redigeringssteget senere.

---

## 10. Avklarte valg og åpne spørsmål

**Avklart:**

- **Skjema klientside i MVP.** Klienten eier spørsmål, rekkefølge og betinget visning; APIet tar imot ferdig svar. Server-levert skjema kan komme senere uten å røre onboarding-endepunktet (§8).
- **Attributt-drevet inkludering innføres samtidig som feltene legges til** – ikke utsatt til v1. MVP-seedingen bruker `ForTypes` + et lite sett `InclusionRule`-betingelser, slik at hvert spørsmål faktisk gir utslag (§7). Klimajustering av intervaller forblir v1.
- **Nye `PropertyAttributes`-felt i MVP:** `Ventilation`, `Driveway`, `Deck` (og `CabinWinterUse` for hytte). Uten dem gir de tilhørende spørsmålene ingen effekt (§7).
- **Rekkehus viser uteblokken** på lik linje med enebolig. Hvert uteelement (hage, oppkjørsel, platting, garasje, vann) gates individuelt med ja/nei, så den blandede rekkehus-virkeligheten fanges uten særbehandling av boligtypen (§4).
- **Matrikkel-prefill i MVP: kun lokasjon/adresse.** Boligtype og byggeår spør vi om direkte; auto-utfylling fra matrikkel utsettes til v1 (§2, plan §8). Reduserer avhengigheten til matrikkeltilgang for MVP.

**Åpne:**

- **Minste nyttige sett – testes i MVP.** Vi bruker MVP-en aktivt til å prøve ut ulike spørsmålssett og se hvor få spørsmål vi kan komme unna med og fortsatt seede en plan brukeren opplever som treffsikker. At skjemaet er klientside (over) gjør slik eksperimentering billig. (Åpent også i MVP §16.) Verdt å tenke på fra start: hvordan vi måler «treffsikkert» – f.eks. hvor mye eier endrer i redigeringssteget (mange fjerninger = for brede spørsmål; mange tillegg = for smale).
- **Matrikkel-prefill (v1):** når adresseoppslag mot matrikkel innføres, hvilke felt tør vi auto-utfylle vs. bare foreslå for brukeren å bekrefte?
