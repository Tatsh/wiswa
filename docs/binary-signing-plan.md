# Plan: Signing PyInstaller Binaries

This document outlines how to sign PyInstaller-built executables so that Windows and macOS do not
show security warnings on launch. It covers both GitHub CI integration and the non-programmatic
steps required.

---

## 1. Overview by Platform

| Platform    | Warning / behavior                                             | Mitigation                                                                                                                                                              |
| ----------- | -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Windows** | SmartScreen: "Windows protected your PC" / "Unknown publisher" | Authenticode code signing with a certificate from a trusted CA (or self-signed for testing). Optional: timestamp so the signature remains valid after the cert expires. |
| **macOS**   | Gatekeeper: "unidentified developer" / "cannot be opened"      | Code sign with a **Developer ID Application** certificate. For smooth distribution, **notarize** the app so users don't need to use "Open Anyway".                      |

Linux binaries are not signed in the same way; this plan focuses on Windows and macOS.

---

## 2. Windows: Authenticode Signing

### 2.1 Non-programmatic steps

1. **Obtain a code-signing certificate**
   - **Production (recommended):** Buy an **OV (Organization Validation)** or **EV (Extended
     Validation)** code-signing certificate from a public CA (e.g. DigiCert, Sectigo, SSL.com). EV
     certs build SmartScreen reputation faster and reduce "Unknown publisher" warnings.
   - **Testing / internal:** Create a self-signed code-signing certificate with `makecert` /
     `certreq` or PowerShell. Users will still see a warning unless they install the root in their
     trust store.

2. **Export the certificate**
   - Export the cert (and private key) as a **PFX (.pfx / .p12)** file.
   - Remember the PFX password; you will store it securely for CI.

3. **Optional: Choose a timestamp server**
   - Use an RFC 3161 timestamp server (e.g. `http://timestamp.digicert.com`,
     `http://timestamp.sectigo.com`) so signatures stay valid after the certificate expires.

### 2.2 GitHub CI: secrets

Add these as **repository** (or **organization**) secrets:

| Secret name                   | Description             | Example                                                                                                                       |
| ----------------------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `WINDOWS_SIGNING_CERTIFICATE` | Base64-encoded PFX file | Output of `base64 -w0 your-cert.pfx` (Linux) or `[Convert]::ToBase64String([IO.File]::ReadAllBytes("cert.pfx"))` (PowerShell) |
| `WINDOWS_SIGNING_PASSWORD`    | Password for the PFX    | (your PFX password)                                                                                                           |

Optional, if using a custom timestamp server:

| Secret name             | Description                                                          |
| ----------------------- | -------------------------------------------------------------------- |
| `WINDOWS_TIMESTAMP_URL` | RFC 3161 timestamp server URL (e.g. `http://timestamp.digicert.com`) |

### 2.3 GitHub CI: workflow changes

- **When to sign:** Only on **tag** pushes (e.g. `v*.*.*`) when creating release artifacts, so you
  don't consume certificate operations on every branch build.
- **Where:** Add a step **after** "Build with PyInstaller" and **before** "Test binary", but only
  when the cert secrets are present (or use a dedicated "sign" job that runs only on tag and when
  secrets exist).
- **Steps:**
  1. Decode the PFX from `WINDOWS_SIGNING_CERTIFICATE` and write to a file.
  2. Use **signtool** (from Windows SDK / Build Tools) or **osslsigncode** to sign each `dist/*.exe`:
     - **signtool:** e.g.

       ```cmd
       signtool sign /f cert.pfx /p %WINDOWS_SIGNING_PASSWORD% /tr %WINDOWS_TIMESTAMP_URL% /td sha256 /fd sha256 dist\script_name.exe
       ```

     - **osslsigncode:** useful if you want a single cross-platform signing script; Windows runners
       can use it via Chocolatey or a pre-built binary.

  3. Do **not** commit or log the PFX or password; use `run` with env from secrets and avoid
     echoing secrets.

**Workflow structure idea (Windows matrix only, on tag):**

```yaml
- if: (matrix.os == 'windows-latest' || matrix.os == 'windows-11-arm') && github.ref_type == 'tag'
  name: 'Sign Windows binaries'
  env:
    SIGNING_CERT_BASE64: ${{ secrets.WINDOWS_SIGNING_CERTIFICATE }}
    SIGNING_PASSWORD: ${{ secrets.WINDOWS_SIGNING_PASSWORD }}
    TIMESTAMP_URL: ${{ secrets.WINDOWS_TIMESTAMP_URL }}
  run: |
    # Decode PFX, then for each dist\*.exe run signtool (or osslsigncode)
    # Only run if SIGNING_CERT_BASE64 is non-empty
```

- **Permissions:** No extra workflow permissions needed beyond what you already have for release
  uploads.
- **Templates (wiswa):** If this is implemented in the shared PyInstaller template (e.g.
  `pyinstaller.yml.j2` and build script), make the signing step **optional** and only run when a
  flag or secret is set (e.g. `settings.pyinstaller.sign_windows` or presence of
  `WINDOWS_SIGNING_CERTIFICATE`), so projects that don't have a cert don't fail.

---

## 3. macOS: Code signing and notarization

### 3.1 Non-programmatic steps

1. **Enroll in Apple Developer Program**
   - Cost: about $99/year.
   - Needed for **Developer ID Application** certificate and notarization.

2. **Create certificates in Apple Developer portal**
   - In Certificates, Identifiers & Profiles -> Certificates, create a **Developer ID Application**
     certificate (for distribution outside the App Store).
   - Download and install it in Keychain Access, then export as a **.p12** (PKCS#12) file with a
     password. This is what CI will use.

3. **Notarization**
   - **Apple ID:** The Apple ID associated with the developer account.
   - **App-specific password:** Create one in Apple ID account -> Sign-In and Security -> App-Specific
     Passwords. CI will use this to submit for notarization.
   - **Team ID:** From the Apple Developer membership page or Xcode. Required for `xcrun notarytool`
     / `altool`.

4. **Keychain and identity**
   - Signing identity is usually something like `"Developer ID Application: Your Name (TEAM_ID)"`.
     You'll pass this to `codesign -s "<identity>"`.

### 3.2 GitHub CI: secrets

Add these as **repository** (or **organization**) secrets:

| Secret name                   | Description                                                                                   |
| ----------------------------- | --------------------------------------------------------------------------------------------- |
| `APPLE_SIGNING_CERTIFICATE`   | Base64-encoded .p12 file (e.g. `base64 -i certificate.p12 -o /dev/stdout \| tr -d '\n'`)      |
| `APPLE_SIGNING_PASSWORD`      | Password for the .p12                                                                         |
| `APPLE_SIGNING_IDENTITY`      | Full name of the code-signing identity (e.g. `Developer ID Application: Your Name (TEAM_ID)`) |
| `APPLE_ID`                    | Apple ID email used for notarization                                                          |
| `APPLE_APP_SPECIFIC_PASSWORD` | App-specific password for that Apple ID                                                       |
| `APPLE_TEAM_ID`               | Team ID (10-character string)                                                                 |

### 3.3 GitHub CI: workflow changes

- **When:** Only on **tag** pushes when building release artifacts (same as Windows).
- **Where:** Add steps **after** "Build with PyInstaller" and **before** "Zip files" on macOS
  matrix jobs.
- **Steps:**
  1. **Import certificate:** Decode `APPLE_SIGNING_CERTIFICATE` to a .p12 file, then import into a
     temporary keychain and set keychain password (e.g. `security create-keychain`,
     `security unlock-keychain`,
     `security import cert.p12 -k keychain -P $APPLE_SIGNING_PASSWORD -T /usr/bin/codesign -T /usr/bin/security`).
  2. **Sign:** For each binary in `dist/` (excluding non-executables like `index.js`), run:
     - `codesign --force --options runtime --sign "$APPLE_SIGNING_IDENTITY" --timestamp path/to/binary`
     - `--options runtime` enables Hardened Runtime (required for notarization).
  3. **Notarize:**
     - Zip the signed binaries (or the app bundle if you had one).
     - Submit with

       ```shell
       xcrun notarytool submit zipfile.zip --apple-id "$APPLE_ID" --password "$APPLE_APP_SPECIFIC_PASSWORD" --team-id "$APPLE_TEAM_ID" --wait
       ```

     - Staple the ticket: `xcrun stapler staple path/to/binary` for each binary (or to the zip if
       notarytool accepts it; typically you staple to the binary or app).

  4. **Clean:** Remove the temporary keychain and avoid logging secrets.

**Workflow structure idea (macOS matrix only, on tag):**

```yaml
- if: (matrix.os == 'macos-latest' || matrix.os == 'macos-15-intel') && github.ref_type == 'tag'
  name: 'Sign and notarize macOS binaries'
  env:
    APPLE_SIGNING_CERTIFICATE: ${{ secrets.APPLE_SIGNING_CERTIFICATE }}
    APPLE_SIGNING_PASSWORD: ${{ secrets.APPLE_SIGNING_PASSWORD }}
    APPLE_SIGNING_IDENTITY: ${{ secrets.APPLE_SIGNING_IDENTITY }}
    APPLE_ID: ${{ secrets.APPLE_ID }}
    APPLE_APP_SPECIFIC_PASSWORD: ${{ secrets.APPLE_APP_SPECIFIC_PASSWORD }}
    APPLE_TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
  run: |
    # Create keychain, import .p12, sign dist/*, zip, notarize, staple
    # Only run if APPLE_SIGNING_CERTIFICATE is non-empty
```

- **Templates (wiswa):** Make signing/notarization optional (e.g. only when
  `APPLE_SIGNING_CERTIFICATE` or a setting like `settings.pyinstaller.sign_macos` is set) so
  projects without Apple certs still build.

---

## 4. Summary: what to add in GitHub

### 4.1 Secrets (per repository or org)

- **Windows:** `WINDOWS_SIGNING_CERTIFICATE`, `WINDOWS_SIGNING_PASSWORD`; optional:
  `WINDOWS_TIMESTAMP_URL`.
- **macOS:** `APPLE_SIGNING_CERTIFICATE`, `APPLE_SIGNING_PASSWORD`, `APPLE_SIGNING_IDENTITY`,
  `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`.

### 4.2 Workflow / template changes

- **PyInstaller workflow** (and wiswa template `pyinstaller.yml.j2`):
  - Insert a **Windows** signing step (decode PFX, run signtool/osslsigncode on `dist/*.exe`) when
    `github.ref_type == 'tag'` and the Windows cert secret is set.
  - Insert **macOS** steps: import .p12 -> codesign with Hardened Runtime -> notarize -> staple,
    when `github.ref_type == 'tag'` and the Apple cert secret is set.
- **Conditional execution:** Use `if: ... && secrets.WINDOWS_SIGNING_CERTIFICATE != ''` (or
  equivalent) so that:
  - Repos **with** secrets get signing on tag builds.
  - Repos **without** secrets do not fail and keep current behavior (unsigned artifacts).

### 4.3 Optional: wiswa jsonnet settings

In `wiswa-jsonnet` (e.g. `defaults.libjsonnet`), you could add:

- `pyinstaller.sign_windows`: boolean, default `false` - "Whether to sign Windows binaries in CI
  (requires secrets)."
- `pyinstaller.sign_macos`: boolean, default `false` - "Whether to sign and notarize macOS binaries
  in CI (requires secrets)."

The template would then run the signing steps only when the corresponding flag is true (and
optionally when the matching secret is present).

---

## 5. Non-programmatic checklist

- [ ] **Windows**
  - [ ] Obtain code-signing certificate (CA or self-signed).
  - [ ] Export PFX and note password.
  - [ ] (Optional) Choose timestamp server.
  - [ ] Add base64 PFX and password to GitHub secrets.
- [ ] **macOS**
  - [ ] Enroll in Apple Developer Program.
  - [ ] Create Developer ID Application certificate; export .p12.
  - [ ] Create app-specific password for notarization.
  - [ ] Add .p12 (base64), password, identity, Apple ID, app-specific password, and Team ID to
        GitHub secrets.
- [ ] **CI**
  - [ ] Add signing steps to PyInstaller workflow (and optionally to wiswa template) with
        conditionals so builds don't fail when secrets are missing.
  - [ ] Test on a tag push: confirm Windows binaries are Authenticode-signed and macOS binaries are
        signed and notarized, and that OS warnings are gone (or reduced) on launch.

---

## 6. References

- **Windows:** [SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool),
  [Authenticode](https://learn.microsoft.com/en-us/windows/win32/seccrypto/authenticode-signing).
- **macOS:** [Code Signing Guide](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Introduction/Introduction.html),
  [Notarization](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution),
  [notarytool](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution/customizing_the_notarization_workflow).
