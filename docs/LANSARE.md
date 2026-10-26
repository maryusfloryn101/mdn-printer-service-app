# Lansarea unei versiuni noi (runbook)

Folosiți acest document de fiecare dată când publicați o versiune nouă a aplicației.

## Ce trebuie să aveți
- acces de scriere la depozitul `maryusfloryn101/mdn-printer-service-app` pe GitHub;
- nimic altceva: installerele se construiesc automat, iar site-ul și aplicațiile instalate le găsesc singure.

## Pași
1. **Numărul versiunii.** În `app/backend/config.py` schimbați `VERSION = "X.Y.Z"` (de ex. din `1.1.0` în `1.1.1`). Regulă: ultima cifră pentru reparații, cifra din mijloc pentru funcții noi.
2. **Noutățile.** Scrieți în `packaging/NOTE_VERSIUNE.md` 1–3 propoziții, în română, despre ce s-a schimbat. Textul apare în aplicații, în bara verde de actualizare, și pe pagina versiunii pe GitHub.
3. **Construirea.** Pe GitHub: fila **Actions** → **Build** → **Run workflow** → **Run workflow**. Durează aproximativ 25 de minute.
4. **Verificarea.** La final, fila **Releases** are versiunea nouă cu 4 fișiere:
   - `MDN-Printer-Service-Setup.exe` (Windows)
   - `MDN-Printer-Service-macOS-AppleSilicon.dmg`
   - `MDN-Printer-Service-macOS-Intel.dmg`
   - `MDN-Printer-Service-Linux-x86_64.AppImage`
5. **Gata.** În cel mult 10 minute:
   - butoanele de descărcare de pe printer.mdndigital.ro duc la versiunea nouă (redirecționare către `releases/latest`);
   - aplicațiile instalate afișează bara „Versiunea X este disponibilă” (manifestul `printer.mdndigital.ro/versiune.json` se reface din GitHub la 10 minute).

## Dacă ceva nu merge
| Problemă | Ce faceți |
|---|---|
| Un job din Actions e roșu | Deschideți jobul, citiți pasul roșu. Apăsați **Re-run failed jobs**; fișierele deja publicate se înlocuiesc. |
| Lipsește un fișier din Release | Rulați din nou workflow-ul; fiecare job își încarcă singur fișierul. |
| Aplicațiile nu văd versiunea nouă | Deschideți `https://printer.mdndigital.ro/versiune.json`: trebuie să arate noul număr. Dacă nu, așteptați 10 minute (cache). |
| Vreți să retrageți o versiune | Pe GitHub, Releases → versiunea → **Delete**. Butoanele de pe site trec automat pe versiunea anterioară. |

## Ce NU intră în depozit
- pașii plătiți ai ghidurilor Canon/Brother (stau doar pe server, în `mdnps/guides.json`);
- cheile serverului de licențe și orice parolă.
