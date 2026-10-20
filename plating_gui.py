"""Tkinter front end for the electroplating calculator. Run: python plating_gui.py"""
from __future__ import annotations

import math
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import plating
from plating import Metal

CUSTOM_LABEL = "Custom…"

CURRENT_SCALE = [(1.0, "A"), (1e-3, "mA"), (1e-6, "µA")]
MASS_SCALE = [(1.0, "g"), (1e-3, "mg"), (1e-6, "µg")]


def fmt(value: float, sig: int = 4) -> str:
    """Format to `sig` significant figures, using exponents only for extreme magnitudes."""
    if value == 0 or not math.isfinite(value):
        return f"{value:g}"
    magnitude = math.floor(math.log10(abs(value)))
    if -4 <= magnitude < 7:
        return f"{value:.{max(sig - 1 - magnitude, 0)}f}"
    return f"{value:.{sig - 1}e}"


def fmt_scaled(value: float, scale: list[tuple[float, str]]) -> str:
    """Format with the largest unit prefix that keeps the number >= 1."""
    for factor, symbol in scale:
        if abs(value) >= factor:
            break
    return f"{fmt(value / factor)} {symbol}"


def fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{fmt(seconds)} s"
    hours, rem = divmod(round(seconds), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours} h {minutes:02d} min {secs:02d} s   ({fmt(seconds / 3600)} h)"
    return f"{minutes} min {secs:02d} s   ({fmt(seconds / 60)} min)"


class QuantityField:
    """A labelled numeric entry with a unit selector.

    Changing the unit converts the entered value so the physical quantity is preserved.
    """

    def __init__(self, parent, row, name, units, value, unit, on_change):
        self.name = name
        self.units = units
        self.value = tk.StringVar(value=value)
        self.unit = tk.StringVar(value=unit)
        self._prev_unit = unit
        self._on_change = on_change

        ttk.Label(parent, text=name).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)
        self.entry = ttk.Entry(parent, textvariable=self.value, width=14, justify="right")
        self.entry.grid(row=row, column=1, sticky="ew", pady=3)
        self.combo = ttk.Combobox(
            parent, textvariable=self.unit, values=list(units), state="readonly", width=8
        )
        self.combo.grid(row=row, column=2, sticky="w", padx=(6, 0), pady=3)
        self.combo.bind("<<ComboboxSelected>>", self._unit_changed)
        self.value.trace_add("write", lambda *_: on_change())

    def _unit_changed(self, _event=None):
        new_unit = self.unit.get()
        try:
            value = float(self.value.get())
        except ValueError:
            pass
        else:
            base = value * self.units[self._prev_unit]
            self.value.set(f"{base / self.units[new_unit]:.6g}")
        self._prev_unit = new_unit
        self._on_change()

    def base_value(self) -> float:
        """The entered value converted to the base unit."""
        try:
            value = float(self.value.get())
        except ValueError:
            raise ValueError(f"{self.name}: enter a number.") from None
        return value * self.units[self.unit.get()]

    def set_entry_enabled(self, enabled: bool) -> None:
        self.entry.configure(state="normal" if enabled else "disabled")


class PlatingCalculator(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=12)
        self.metals = {m.label: m for m in plating.METALS}
        # Efficiency is remembered per metal so a bath-specific fudge factor survives switching.
        self.efficiencies = {label: m.typical_efficiency for label, m in self.metals.items()}
        self.efficiencies[CUSTOM_LABEL] = 100.0
        self._syncing_efficiency = False
        self._ready = False
        self._last_summary = ""

        self._configure_styles()
        self.columnconfigure(0, weight=1)
        self._build_metal_section()
        self._build_process_section()
        self._build_results_section()

        self._ready = True
        self._metal_changed()
        self._mode_changed()

    # ----------------------------------------------------------------- layout
    def _configure_styles(self):
        style = ttk.Style(self)
        bold = tkfont.nametofont("TkDefaultFont").copy()
        bold.configure(weight="bold")
        big = bold.copy()
        big.configure(size=bold.cget("size") + 2)
        style.configure("Result.TLabel", font=bold)
        style.configure("Answer.TLabel", font=big, foreground="#0b5394")
        style.configure("Info.TLabel", foreground="#555555")
        style.configure("Error.TLabel", foreground="#b00020")

    def _build_metal_section(self):
        frame = ttk.LabelFrame(self, text="Metal", padding=10)
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Metal / ion").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.metal = tk.StringVar(value=plating.METALS[0].label)
        self._prev_metal = self.metal.get()
        combo = ttk.Combobox(
            frame,
            textvariable=self.metal,
            values=[*self.metals, CUSTOM_LABEL],
            state="readonly",
            width=24,
        )
        combo.grid(row=0, column=1, sticky="w")
        combo.bind("<<ComboboxSelected>>", lambda _e: self._metal_changed())

        self.metal_info = tk.StringVar()
        ttk.Label(frame, textvariable=self.metal_info, style="Info.TLabel", justify="left").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )

        self.custom_frame = ttk.Frame(frame)
        self.custom_frame.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.custom_molar_mass = tk.StringVar(value="58.69")
        self.custom_electrons = tk.StringVar(value="2")
        self.custom_density = tk.StringVar(value="8.9")
        for col, (label, var, unit) in enumerate(
            [
                ("Molar mass", self.custom_molar_mass, "g/mol"),
                ("Electrons", self.custom_electrons, "e⁻"),
                ("Density", self.custom_density, "g/cm³"),
            ]
        ):
            ttk.Label(self.custom_frame, text=label).grid(row=0, column=col * 3, padx=(0 if col == 0 else 12, 4))
            ttk.Entry(self.custom_frame, textvariable=var, width=8, justify="right").grid(row=0, column=col * 3 + 1)
            ttk.Label(self.custom_frame, text=unit).grid(row=0, column=col * 3 + 2, padx=(3, 0))
            var.trace_add("write", lambda *_: self.recalculate())

    def _build_process_section(self):
        frame = ttk.LabelFrame(self, text="Process", padding=10)
        frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Solve for").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.solve_for = tk.StringVar(value="time")
        modes = ttk.Frame(frame)
        modes.grid(row=0, column=1, columnspan=3, sticky="w", pady=(0, 4))
        for text, value in [("Plating time", "time"), ("Thickness", "thickness")]:
            ttk.Radiobutton(
                modes, text=text, value=value, variable=self.solve_for, command=self._mode_changed
            ).pack(side="left", padx=(0, 12))

        rc = self.recalculate
        self.area = QuantityField(frame, 1, "Area", plating.AREA_UNITS, "10", "cm²", rc)
        self.thickness = QuantityField(frame, 2, "Thickness", plating.THICKNESS_UNITS, "10", "µm", rc)
        self.time = QuantityField(frame, 3, "Plating time", plating.TIME_UNITS, "60", "min", rc)
        self.current_density = QuantityField(
            frame, 4, "Current density", plating.CURRENT_DENSITY_UNITS, "20", "mA/cm²", rc
        )

        ttk.Label(frame, text="Efficiency").grid(row=5, column=0, sticky="w", padx=(0, 10), pady=3)
        initial = self.efficiencies[self.metal.get()]
        self.efficiency = tk.StringVar(value=f"{initial:g}")
        ttk.Entry(frame, textvariable=self.efficiency, width=14, justify="right").grid(
            row=5, column=1, sticky="ew", pady=3
        )
        ttk.Label(frame, text="%").grid(row=5, column=2, sticky="w", padx=(6, 0))
        self.efficiency_slider = tk.DoubleVar(value=initial)
        ttk.Scale(
            frame,
            from_=1,
            to=100,
            variable=self.efficiency_slider,
            command=self._efficiency_slid,
        ).grid(row=6, column=1, columnspan=2, sticky="ew")
        ttk.Button(frame, text="Reset to typical", command=self._reset_efficiency).grid(
            row=6, column=3, sticky="e", padx=(10, 0)
        )
        self.efficiency.trace_add("write", self._efficiency_typed)

    def _build_results_section(self):
        frame = ttk.LabelFrame(self, text="Results", padding=10)
        frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        frame.columnconfigure(1, weight=1)

        self.answer_name = tk.StringVar()
        self.answer = tk.StringVar()
        ttk.Label(frame, textvariable=self.answer_name, style="Answer.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 16), pady=(0, 6)
        )
        ttk.Label(frame, textvariable=self.answer, style="Answer.TLabel").grid(
            row=0, column=1, sticky="w", pady=(0, 6)
        )

        self.result_vars = {}
        for row, name in enumerate(
            ["Total current", "Deposition rate", "Charge passed", "Deposit mass"], start=1
        ):
            ttk.Label(frame, text=name).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=2)
            var = tk.StringVar()
            ttk.Label(frame, textvariable=var, style="Result.TLabel").grid(
                row=row, column=1, sticky="w", pady=2
            )
            self.result_vars[name] = var

        bottom = ttk.Frame(frame)
        bottom.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(0, weight=1)
        self.status = tk.StringVar()
        self.status_label = ttk.Label(bottom, textvariable=self.status, wraplength=320)
        self.status_label.grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="Copy results", command=self._copy_results).grid(
            row=0, column=1, sticky="e"
        )

    # -------------------------------------------------------------- handlers
    def _metal_changed(self):
        label = self.metal.get()
        self.efficiencies[self._prev_metal] = self._efficiency_value_or(
            self.efficiencies[self._prev_metal]
        )
        self._prev_metal = label
        self.efficiency.set(f"{self.efficiencies[label]:g}")

        if label == CUSTOM_LABEL:
            self.custom_frame.grid()
            self.metal_info.set("Enter molar mass, electrons transferred per atom, and deposit density.")
        else:
            self.custom_frame.grid_remove()
            m = self.metals[label]
            self.metal_info.set(
                f"M = {m.molar_mass:g} g/mol    n = {m.electrons} e⁻    ρ = {m.density:g} g/cm³\n"
                f"Typical efficiency ≈ {m.typical_efficiency:g} %  ({m.bath})"
            )
        self.recalculate()

    def _mode_changed(self):
        solving_time = self.solve_for.get() == "time"
        self.thickness.set_entry_enabled(solving_time)
        self.time.set_entry_enabled(not solving_time)
        self.recalculate()

    def _efficiency_value_or(self, default: float) -> float:
        try:
            return float(self.efficiency.get())
        except ValueError:
            return default

    def _efficiency_slid(self, value):
        if self._syncing_efficiency:
            return
        self._syncing_efficiency = True
        self.efficiency.set(f"{float(value):.0f}")
        self._syncing_efficiency = False
        self.recalculate()

    def _efficiency_typed(self, *_):
        if not self._syncing_efficiency:
            try:
                value = float(self.efficiency.get())
            except ValueError:
                pass
            else:
                self._syncing_efficiency = True
                self.efficiency_slider.set(min(max(value, 1), 100))
                self._syncing_efficiency = False
        self.recalculate()

    def _reset_efficiency(self):
        label = self.metal.get()
        typical = 100.0 if label == CUSTOM_LABEL else self.metals[label].typical_efficiency
        self.efficiency.set(f"{typical:g}")

    # ----------------------------------------------------------- calculation
    def _current_metal(self) -> Metal:
        label = self.metal.get()
        if label != CUSTOM_LABEL:
            return self.metals[label]
        try:
            molar_mass = float(self.custom_molar_mass.get())
            density = float(self.custom_density.get())
            electrons = int(self.custom_electrons.get())
        except ValueError:
            raise ValueError(
                "Custom metal: enter numeric molar mass and density, and a whole number of electrons."
            ) from None
        return Metal("Custom", "custom", molar_mass, electrons, density, 100.0)

    def recalculate(self, *_):
        if not self._ready:
            return
        try:
            metal = self._current_metal()
            area = self.area.base_value()
            current_density = self.current_density.base_value()
            try:
                efficiency = float(self.efficiency.get()) / 100
            except ValueError:
                raise ValueError("Efficiency: enter a number.") from None
            if self.solve_for.get() == "time":
                result = plating.solve(
                    metal, area, current_density, efficiency, thickness=self.thickness.base_value()
                )
            else:
                result = plating.solve(
                    metal, area, current_density, efficiency, time=self.time.base_value()
                )
        except ValueError as exc:
            self._show_error(str(exc))
            return
        self._show_result(metal, result)

    def _show_error(self, message: str):
        self.answer.set("—")
        for var in self.result_vars.values():
            var.set("—")
        self.status.set(message)
        self.status_label.configure(style="Error.TLabel")
        self._last_summary = ""

    def _show_result(self, metal: Metal, r: plating.Result):
        t_unit = self.thickness.unit.get()
        t_factor = plating.THICKNESS_UNITS[t_unit]
        thickness_text = f"{fmt(r.thickness / t_factor)} {t_unit}"
        time_text = fmt_duration(r.time)

        if self.solve_for.get() == "time":
            self.answer_name.set("Plating time")
            self.answer.set(time_text)
        else:
            self.answer_name.set("Plated thickness")
            self.answer.set(thickness_text)

        rate_min = r.rate * 60 / t_factor
        values = {
            "Total current": fmt_scaled(r.current, CURRENT_SCALE),
            "Deposition rate": f"{fmt(rate_min)} {t_unit}/min   ({fmt(rate_min * 60)} {t_unit}/h)",
            "Charge passed": f"{fmt(r.charge)} C   ({fmt(r.charge / 3600)} A·h)",
            "Deposit mass": fmt_scaled(r.mass, MASS_SCALE),
        }
        for name, text in values.items():
            self.result_vars[name].set(text)
        self.status.set("")
        self.status_label.configure(style="TLabel")

        metal_desc = (
            self.metal.get()
            if metal.name != "Custom"
            else f"Custom (M = {metal.molar_mass:g} g/mol, n = {metal.electrons}, ρ = {metal.density:g} g/cm³)"
        )
        lines = [
            "Electroplating calculation",
            f"Metal: {metal_desc}",
            f"Area: {self.area.value.get()} {self.area.unit.get()}",
            f"Current density: {self.current_density.value.get()} {self.current_density.unit.get()}",
            f"Efficiency: {self.efficiency.get()} %",
            f"Thickness: {thickness_text}",
            f"Plating time: {time_text}",
            *(f"{name}: {text}" for name, text in values.items()),
        ]
        self._last_summary = "\n".join(lines)

    def _copy_results(self):
        if not self._last_summary:
            return
        self.clipboard_clear()
        self.clipboard_append(self._last_summary)
        self.status.set("Results copied to clipboard.")
        self.status_label.configure(style="TLabel")


def main():
    if sys.platform == "win32":
        try:  # crisp text on high-DPI displays
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    root.title("Electroplating Calculator")
    app = PlatingCalculator(root)
    app.grid(sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    root.update_idletasks()
    root.minsize(root.winfo_reqwidth(), root.winfo_reqheight())
    root.mainloop()


if __name__ == "__main__":
    main()
