# Altiora Confidence

A desktop app for **Windows and Mac** that hides **names, dates, addresses, signatures**, emails, phone numbers and ID numbers (IBAN, CIN, ICE, SIRET) in PDFs.
It runs **100% offline**: no file ever leaves the computer. Hidden text is **deleted** from the file, not just covered.

There are 3 ways to produce the installers:

| | You need | You get |
|---|---|---|
| **A. GitHub (recommended)** | a free GitHub account, no Mac | Mac (Apple chips + Intel) **and** Windows, all at once |
| **B. On a Windows PC** | Python 3.10–3.14 | Windows installer |
| **C. On a Mac** | Python 3.10–3.14 | Mac `.dmg` for that Mac's type |

---

## A. Build everything on GitHub (no Mac needed)

**One-time setup (10 minutes)**
1. Create a free account on https://github.com if you don't have one.
2. Click **+** (top right) → **New repository** → name: `altiora-confidence` → choose **Private** → **Create repository**.
3. On the new page, click **"uploading an existing file"**.
4. Open this `altiora-confidence` folder on your PC, select **everything inside it** (including the `.github` folder) and drag it into the browser page → **Commit changes**.
   *Check afterwards that the `.github` folder appears in the file list. Without it, nothing gets built.*

**Build (each time you want installers)**
1. In your repository, open the **Actions** tab.
2. Click **"Build Altiora Confidence"** on the left → **Run workflow** → **Run workflow**.
3. Wait about 15–25 minutes until the three jobs show a green ✓ (Mac apple-silicon, Mac intel, Windows).
4. Click the finished run and scroll to **Artifacts** to download:
   - `Altiora-Confidence-mac-apple-silicon` → for Macs with M1/M2/M3/M4 chips
   - `Altiora-Confidence-mac-intel` → for older Intel Macs
   - `Altiora-Confidence-windows` → the Windows installer

   Each download is a .zip containing the `.dmg` (Mac) or `Setup_….exe` (Windows).

If a job shows a red ✗, click it: the last step prints the build log. Send me a screenshot.
GitHub keeps artifacts for 90 days. Private repositories include free build minutes every month, enough for many builds.

**Which Mac do I have?**  Apple menu  → *About This Mac*: "Chip: Apple M…" = apple-silicon; "Processor: Intel…" = intel.

---

## B. Build on Windows

1. Before unzipping, right-click the zip → *Propriétés* → tick **Débloquer** → OK. Then unzip.
2. Double-click **`build_windows.bat`** and wait 5–10 minutes (internet needed for this step only).
3. Result: `output\Setup_Altiora_Confidence_1.0.exe`.

## C. Build on a Mac

1. Copy this folder to the Mac.
2. Open **Terminal**, type `bash ` (with a space), drag `build_mac.sh` into the window, press Enter.
3. Result: `output/Altiora_Confidence_1.0_mac_apple-silicon.dmg` (or `_intel`).

---

## Installing on a Mac (for the team)

1. Open the `.dmg` and drag **Altiora Confidence** onto **Applications**.
2. The first time, macOS says it "cannot verify the developer", because the app isn't signed with an Apple Developer account yet:
   - click **Done** (or OK);
   - open  → **System Settings → Privacy & Security**, scroll down, click **Open Anyway** next to "Altiora Confidence", and confirm with your password.

   This is needed only once.
3. You can also drag a PDF onto the app's icon in the Dock, or right-click a PDF → *Ouvrir avec* → Altiora Confidence.

**Removing the Mac warning for good:** join the Apple Developer Program ($99/year). Then on a Mac, set the variables listed at the top of `build_mac.sh` before running it: the app gets signed and notarised by Apple and opens without any warning. Ask me to add this to the GitHub build too.

## Installing on Windows (for the team)

Double-click `Setup_Altiora_Confidence_1.0.exe` → Suivant → Installer. No admin rights or internet needed.
If "Windows a protégé votre ordinateur" appears: *Informations complémentaires* → *Exécuter quand même*.

---

## Using the app (Windows and Mac)
1. **Documents:** drag PDFs (or a folder) into the window, choose what to hide, click **Analyser**.
2. **Vérification:** everything that will be hidden is highlighted.
   - Click a coloured area → it **stays visible**.
   - Click any word → it **gets hidden**.
   - Click and drag → hide a **zone** (signature, stamp…).
   - Missed a name? Type it under **"Un élément a été oublié ?"** → *Masquer partout*.
3. **Terminé:** `…_anonymise.pdf` is saved next to the original (which is never modified), and the app checks that the hidden text is really gone.

Always take a last look at the result before sharing it. Detection is very good but not perfect.

---

## Folder contents
| | |
|---|---|
| `.github/workflows/build.yml` | The GitHub cloud build (Mac + Windows) |
| `build_windows.bat` / `build_mac.sh` | Build on a Windows PC / on a Mac |
| `main.py`, `app/` | The application (interface `gui.py`, detection `engine.py` + `patterns.py`) |
| `packaging/` | Build recipes (PyInstaller, Inno Setup, Mac signing settings) |
| `exemple_contrat.pdf` | Fake contract used for testing and by the automatic check |
