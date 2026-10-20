# Electroplating Calculator

Tkinter GUI for electroplating time / thickness from Faraday's law. No dependencies beyond the Python standard library.

```
python plating_gui.py      # run the app
python -m unittest         # run the tests
```

## Math

Deposition rate (thickness per second):

    rate = j · η · M / (n · F · ρ)

- `j` current density, `η` cathode (faradaic) efficiency, `M` molar mass,
  `n` electrons per atom, `F` = 96485.33 C/mol, `ρ` deposit density.
- Plating time = thickness / rate. Rate and time don't depend on area; total current = j · area.
- "Charge passed" is the total charge including inefficiency losses; "Deposit mass" is the metal actually deposited.

## Notes

- Changing a unit converts the entered value (10 µm → 0.3937 mil) rather than reinterpreting it.
- Efficiency is remembered per metal, so a calibrated fudge factor for one bath survives switching
  metals. "Reset to typical" restores the built-in starting value.
- Built-in typical efficiencies are rough literature starting points; actual values depend strongly
  on bath chemistry, temperature, agitation and current density. Calibrate against a weighed or
  measured test part for anything critical.
- Densities are bulk values; some electrodeposits (e.g. hard gold, trivalent chrome) are less dense.
- Pick "Custom…" to enter molar mass, electrons transferred and density for any other metal or alloy.
