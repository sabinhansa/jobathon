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

The content script injects a floating `JA` button on common job pages. It does not read page text until the user clicks extraction.
