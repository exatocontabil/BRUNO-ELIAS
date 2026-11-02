"""Smoke/behavior tests for V126 Exatinho presence layer.

Run under Xvfb on Linux or on Windows with a normal desktop session.
The test uses a temporary EXATO_DATA_DIR so it does not alter production data.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("EXATO_DATA_DIR", str(Path(tempfile.gettempdir()) / "ExatoCentralFiscal_V126_Test"))
sys.path.insert(0, str(ROOT))

import exato_central_fiscal as m  # noqa: E402


def main() -> None:
    app = m.App()
    observed: list[tuple[str, str]] = []

    def collect() -> None:
        app.update_idletasks()
        observed.append(("greeting", str(app.ia_float_bubble.cget("text"))))
        observed.append(("display_size", str(app._ia_live_display_size)))
        observed.append(("bubble_font", str(app.ia_float_bubble.cget("font"))))
        app._exatinho_demo_humor()
        observed.append(("humor_state", str(app._ia_behavior_state)))
        observed.append(("humor_text", str(app.ia_float_bubble.cget("text"))))
        app.destroy()
        if not observed[0][1]:
            raise AssertionError("Exatinho não apresentou a saudação inicial.")
        if observed[1][1] != "68":
            raise AssertionError(f"Tamanho inesperado do Exatinho: {observed[1][1]}")
        if "9" not in observed[2][1]:
            raise AssertionError(f"Fonte inesperada do balão: {observed[2][1]}")
        if observed[3][1] != "HUMOR":
            raise AssertionError(f"Estado de humor não ativado: {observed[3][1]}")
        print(observed)

    app.after(2800, collect)
    app.mainloop()


if __name__ == "__main__":
    main()
