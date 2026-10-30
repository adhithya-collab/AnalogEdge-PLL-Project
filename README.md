# AnalogEdge - PLL Behavioral Modeling and Verification

Behavioral model of a charge-pump PLL (10 MHz reference, divide-by-10, 100 MHz output)
with lock-time, disturbance and jitter-sensitivity analysis. Persevex VLSI course, Project 1.

## Architecture
PFD -> Charge Pump -> Loop Filter (R + C) -> VCO -> Divide-by-N (feedback)

## Baseline design
| Parameter | Value |
|---|---|
| Reference frequency | 10 MHz |
| Divider N | 10 (output 100 MHz) |
| Charge pump current | 100 uA |
| VCO gain | 50 MHz/V |
| Loop filter | R = 6.26 kOhm, C = 100 pF |
| Damping factor | 0.7 |
| Natural frequency / crossover | 356 kHz / 549 kHz |
| Phase margin | 65 degrees |

## Folder contents
- `AnalogEdge_PLL_Report.pdf` - full report (models, results, sweeps, jitter, guidelines, limitations)
- `PPT/AnalogEdge_PLL_Presentation.pptx` - 10-slide presentation
- `SourceCode/pll_sim.py` - time-domain simulation: lock acquisition, reference step, disturbance
- `SourceCode/pll_analysis.py` - linear model: lock time, overshoot, phase margin and jitter sweeps
- `SourceCode/design.sv`, `SourceCode/testbench.sv` - supplementary SystemVerilog model and testbench
- `Plots/` - result figures
- `Results/` - printed program output

## How to run
```
pip install numpy scipy matplotlib
python SourceCode/pll_sim.py
python SourceCode/pll_analysis.py
```

## Key results
- Locks from 90 MHz to 100 MHz in about 3.0 us (phase error below 0.3 ns for 30 cycles)
- Re-locks to 105 MHz about 2.0 us after a 10 to 10.5 MHz reference step
- A 20 mV control-voltage disturbance kicks the output by 1 MHz; lock regained in about 1.5 us
- Frequency overshoot 22.8% in simulation vs 21% predicted by the linear model
- Lock time is inversely proportional to loop bandwidth
- Damping 0.7 gives the fastest settling (2.3 us, 65 deg margin)
- Jitter minimum about 13.35 ps near 640 kHz under assumed noise (reference -130 dBc/Hz, VCO -110 dBc/Hz at 1 MHz)

## Limitations
Ideal charge pump (no leakage or mismatch), linear behavioral VCO, integer-N only,
second-order loop, assumed noise levels, no process corners.
