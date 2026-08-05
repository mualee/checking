# Starts the Firebase Emulator Suite (auth, firestore, storage, ui) for local dev.
# Run from the repo root:  ./scripts/start_emulators.ps1
# Requires: firebase-tools (npm i -g firebase-tools) and a JDK (for Firestore).
firebase emulators:start --only auth,firestore,storage
