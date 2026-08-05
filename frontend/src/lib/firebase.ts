import { initializeApp } from "firebase/app";
import {
  getAuth,
  connectAuthEmulator,
  setPersistence,
  browserLocalPersistence,
} from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const firebaseApp = initializeApp(firebaseConfig);
export const auth = getAuth(firebaseApp);

// Persist the session in localStorage so a refresh keeps the user signed in.
void setPersistence(auth, browserLocalPersistence);

const emulatorHost = import.meta.env.VITE_AUTH_EMULATOR_HOST;
if (emulatorHost) {
  connectAuthEmulator(auth, `http://${emulatorHost}`, { disableWarnings: true });
}
