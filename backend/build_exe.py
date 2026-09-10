"""Build the local backend into a standalone folder (dist/backend/backend.exe)
via PyInstaller. Run from the frontend as `npm run backend:build`, or directly:

    python build_exe.py

The result is a onedir bundle (faster startup than onefile) that Electron ships
as an extra resource and launches on app start. firebase-admin and the
google-cloud stack are excluded: the local build never initializes Firebase.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import PyInstaller.__main__

HERE = Path(__file__).resolve().parent
ENTRY = HERE / "run_server.py"
# Lao TTF bundled for the PDF report (reportlab needs the file at runtime).
REPORT_FONT = HERE / "app" / "assets" / "fonts" / "PhetsarathOT.ttf"


def build() -> None:
    for d in ("build", "dist"):
        shutil.rmtree(HERE / d, ignore_errors=True)

    args = [
        str(ENTRY),
        "--name=backend",
        "--noconfirm",
        "--clean",
        "--console",
        f"--distpath={HERE / 'dist'}",
        f"--workpath={HERE / 'build'}",
        f"--specpath={HERE}",
        # Packages that ship data files / dynamic imports PyInstaller can miss.
        "--collect-all=uvicorn",
        "--collect-all=pdfplumber",
        "--collect-all=pdfminer",
        "--collect-all=reportlab",
        "--collect-all=docx",
        # Lao font for the PDF report -> _internal/app/assets/fonts/.
        f"--add-data={REPORT_FONT}{os.pathsep}app/assets/fonts",
        # OCR stack for scanned PDFs (bundles the ONNX models + native libs).
        "--collect-all=rapidocr_onnxruntime",
        "--collect-all=onnxruntime",
        "--collect-all=cv2",
        "--collect-all=shapely",
        "--collect-submodules=app",
        # Not needed in local mode — keep the bundle lean and avoid grpc/google pain.
        "--exclude-module=firebase_admin",
        "--exclude-module=google.cloud",
        "--exclude-module=grpc",
    ]
    PyInstaller.__main__.run(args)
    print("\nBuilt:", HERE / "dist" / "backend" / "backend.exe")


if __name__ == "__main__":
    build()
