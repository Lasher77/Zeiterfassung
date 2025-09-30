#!/usr/bin/env python3
"""Utility script to check whether WeasyPrint and its native dependencies are available."""

from __future__ import annotations

import platform
import sys
from textwrap import dedent


def _format_common_guidance() -> str:
    return dedent(
        """
        Allgemeine Tipps:
          • Stelle sicher, dass die systemweiten Bibliotheken nach der Installation
            in Deinem `PATH` (Windows) bzw. den Bibliothekspfaden der Plattform verfügbar sind.
          • Lies die WeasyPrint-Dokumentation zur Fehleranalyse:
            https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#troubleshooting
        """
    ).strip()


def _linux_guidance() -> str:
    return dedent(
        """
        Linux-spezifische Schritte:
          • Debian/Ubuntu: sudo apt install libcairo2 libpango-1.0-0 libgdk-pixbuf2.0-0 libffi-dev
          • Fedora/RHEL:   sudo dnf install cairo pango gdk-pixbuf2 libffi
          • Arch Linux:    sudo pacman -S cairo pango gdk-pixbuf2 libffi
        """
    ).strip()


def _macos_guidance() -> str:
    return dedent(
        """
        macOS-spezifische Schritte:
          • Installiere die nativen Bibliotheken: brew install cairo pango gdk-pixbuf libffi
          • Stelle sicher, dass Homebrew-Bibliotheken gefunden werden, z. B.:
              export DYLD_LIBRARY_PATH="/opt/homebrew/lib:${DYLD_LIBRARY_PATH}"
              export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:${DYLD_FALLBACK_LIBRARY_PATH}"
          • Starte Dein Terminal neu oder hinterlege die Exports dauerhaft in ~/.zshrc bzw. ~/.bash_profile.
        """
    ).strip()


def _windows_guidance() -> str:
    return dedent(
        """
        Windows-spezifische Schritte:
          • Installiere das GTK 64-bit Runtime Bundle (empfohlen von WeasyPrint):
            https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
          • Füge den Installationspfad (z. B. C:\\Program Files\\GTK3-Runtime\\bin) zur PATH-Umgebungsvariable hinzu.
          • Starte die Eingabeaufforderung bzw. PowerShell neu, bevor Du den Check erneut ausführst.
        """
    ).strip()


def _platform_guidance(system_name: str) -> str:
    if system_name == "Darwin":
        return _macos_guidance()
    if system_name == "Windows" or system_name.startswith("CYGWIN") or system_name.startswith("MSYS"):
        return _windows_guidance()
    if system_name == "Linux":
        return _linux_guidance()
    return dedent(
        f"""
        Plattform "{system_name}" wird nicht explizit unterstützt.
        Bitte prüfe die WeasyPrint-Dokumentation für Deine Distribution/Dein Betriebssystem.
        """
    ).strip()


def main() -> int:
    system_name = platform.system()
    try:
        from weasyprint import HTML  # noqa: F401  (Nur Import-Check)
    except ImportError as exc:  # WeasyPrint oder Python-Paket fehlt
        print("❌ WeasyPrint konnte nicht importiert werden (ImportError).")
        print(f"Details: {exc}")
        print()
        print("👉 Nächste Schritte:")
        print(_platform_guidance(system_name))
        print()
        print(_format_common_guidance())
        return 1
    except OSError as exc:  # Native Bibliotheken fehlen oder sind nicht auffindbar
        print("❌ WeasyPrint wurde gefunden, aber native Bibliotheken fehlen oder sind nicht ladbar (OSError).")
        print(f"Details: {exc}")
        print()
        print("👉 Nächste Schritte:")
        print(_platform_guidance(system_name))
        print()
        print(_format_common_guidance())
        return 1

    print("✅ WeasyPrint und die erforderlichen nativen Bibliotheken scheinen verfügbar zu sein.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
