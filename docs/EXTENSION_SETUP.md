# Extension Setup

Build:

```powershell
cd extension
npm install
npm run build
```

Load:

1. Open Opera GX or Chrome extensions.
2. Enable developer mode.
3. Load unpacked.
4. Select `extension/dist`.

Permissions:

- `activeTab`: lets the user explicitly extract visible text from the current tab.
- `scripting`: used by the popup extraction button.
- `storage`: stores local backend URL.
- Host permissions are limited to localhost backend URLs.

The content script opens a compact right-side Jobathon drawer on common job pages and leaves a floating `JA` button for reopening it after closing. It does not read page text until the user clicks extraction.
