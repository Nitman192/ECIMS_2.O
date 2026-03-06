from __future__ import annotations

import threading
import time


def trigger_mass_storage_block_alarm(message: str) -> None:
    _play_alarm_tone()
    _show_popup_async(
        title="ECIMS Security Alert",
        message=message,
    )


def _play_alarm_tone() -> None:
    try:
        import winsound

        pattern = [(1400, 180), (950, 180), (1400, 220)]
        for freq, duration in pattern:
            winsound.Beep(freq, duration)
        return
    except Exception:
        pass

    try:
        # Fallback beep if frequency tone is unavailable.
        import winsound

        for _ in range(3):
            winsound.MessageBeep(winsound.MB_ICONHAND)
            time.sleep(0.12)
    except Exception:
        return


def _show_popup_async(*, title: str, message: str) -> None:
    thread = threading.Thread(target=_show_popup, args=(title, message), daemon=True)
    thread.start()


def _show_popup(title: str, message: str) -> None:
    try:
        import ctypes

        MB_OK = 0x00000000
        MB_ICONERROR = 0x00000010
        MB_TOPMOST = 0x00040000
        ctypes.windll.user32.MessageBoxW(None, message, title, MB_OK | MB_ICONERROR | MB_TOPMOST)
    except Exception:
        return
