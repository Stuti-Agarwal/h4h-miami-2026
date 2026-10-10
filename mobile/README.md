# SombraRoute mobile app (Capacitor)

A thin native shell around the web UI. Scoring and Gemma calls run in the Flask
server, so the app just loads the UI from a running server (`server.url`).
`www/` only holds an offline fallback page.

## Prerequisites
- Node 18+ and npm
- iOS: Xcode (full app, not just Command Line Tools). Uses Swift Package Manager, no CocoaPods.
- Android: Android Studio (SDK + JDK 17+)
- The server running: `python -m app.server` (port 5050)

## Run
```bash
cd mobile
npm install
# edit capacitor.config.json -> server.url (see below)
npx cap sync
npx cap open ios       # or: npx cap open android
```
Then press Run in Xcode / Android Studio.

## Setting server.url
`capacitor.config.json` defaults to `http://localhost:5050`, which works in the
iOS Simulator. Anywhere else, point it at a reachable address:
- Physical phone on the same Wi-Fi: `http://<laptop-ip>:5050` (find it with `ipconfig getifaddr en0`).
  The server already binds `0.0.0.0`; allow it through the macOS firewall if prompted.
- Android emulator: `http://10.0.2.2:5050`
- Deployed: `https://your-host`. You can drop `cleartext: true` once it's HTTPS.

Run `npx cap sync` after every change to the config.

`cleartext: true` (Android) and `NSAllowsLocalNetworking` in `ios/App/App/Info.plist`
let plain HTTP work for local/LAN development.

## Icons
The iOS icon is copied from `app/static/icon-512.png`. Android still has the default
Capacitor icon; run `npx @capacitor/assets generate` to make all sizes.

## No-install alternative (PWA)
Open the server URL in Safari/Chrome on the phone, then Share -> Add to Home Screen.
