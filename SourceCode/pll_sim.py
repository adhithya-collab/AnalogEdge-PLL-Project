# =====================================================================
# AnalogEdge - PLL time-domain behavioural simulation (Python)
# Same PLL as the SystemVerilog model: PFD -> charge pump -> R/C loop
# filter -> VCO -> divide-by-N. Runs in Google Colab (no install needed).
#
# Model (evaluated once per reference cycle, exact for a tri-state PFD):
#   e   = ref phase - (VCO phase / N)           [reference cycles]
#   Q   = ICP * Tref * clip(e, -1, 1)           [charge pump pulse charge]
#   vc += Q / C                                  [capacitor integrates]
#   VCO phase += KVCO*R*Q                        [R * Icp proportional path]
#   VCO phase += f_vco * Tref                    [VCO runs until next edge]
# =====================================================================
# %% Parameters
import os
import numpy as np
import matplotlib
if os.environ.get("NO_DISPLAY"):
    matplotlib.use("Agg")
import matplotlib.pyplot as plt

N      = 10            # divider -> 100 MHz from 10 MHz
FREF0  = 10e6          # reference frequency (Hz)
ICP    = 100e-6        # charge pump current (A)
KVCO   = 50e6          # VCO gain (Hz/V)
F0     = 100e6         # VCO frequency at VC0 (Hz)
VC0    = 1.0           # control voltage for F0 (V)
VINIT  = 0.8           # initial capacitor voltage (V) -> VCO starts at 90 MHz
ZETA   = 0.7
LOCK_NS, LOCK_CYCLES = 0.3, 30      # lock rule: |phase error| < 0.3 ns for 30 cycles

os.makedirs("plots", exist_ok=True)

def design(fn, zeta=ZETA):
    """R, C that give natural frequency fn (Hz) and damping zeta."""
    wn = 2*np.pi*fn
    C = ICP*(2*np.pi*KVCO)/(2*np.pi*N*wn**2)
    R = 2*zeta/(wn*C)
    return R, C

# %% Simulation
def simulate(fn=356e3, zeta=ZETA, t_end=80e-6, events=True):
    R, C = design(fn, zeta)
    vc, phi, t, k = VINIT, 0.0, 0.0, 0     # phi = VCO phase in cycles
    T, VC, F, E = [], [], [], []
    while t < t_end:
        fref = 10.5e6 if (events and t >= 30e-6) else FREF0       # reference step
        vd   = 0.02   if (events and 50e-6 <= t < 55e-6) else 0.0  # supply disturbance (V)
        Tref = 1.0/fref
        e = k - phi/N                              # phase error (reference cycles)
        Q = ICP*Tref*np.clip(e, -1.0, 1.0)         # charge from the pump this cycle
        vc  += Q/C
        vc   = min(max(vc, 0.0), 2.0)
        phi += KVCO*R*Q                            # proportional-path phase kick
        f = F0 + KVCO*(vc + vd - VC0)              # VCO frequency this cycle
        f_eff = f + KVCO*R*Q/Tref                  # average VCO frequency this cycle (integral + proportional path)
        T.append(t*1e6); VC.append(vc); F.append(f_eff/1e6); E.append(e*Tref*1e9)
        phi += f*Tref
        t += Tref; k += 1
    return np.array(T), np.array(VC), np.array(F), np.array(E)

def lock_times(T, E):
    """Return the times (us) at which a lock streak starts."""
    good, locked, events_ = 0, False, []
    for i, e in enumerate(E):
        if abs(e) < LOCK_NS:
            good += 1
            if good == LOCK_CYCLES and not locked:
                locked = True; events_.append(float(T[i-LOCK_CYCLES+1]))
        else:
            good, locked = 0, False
    return events_

# %% Run baseline and plot
T, VC, F, E = simulate()
lt = lock_times(T, E)
print("Lock streaks start at (us):", [round(x, 2) for x in lt])
print(f"Initial acquisition lock time: {lt[0]:.2f} us")
print(f"Final VCO frequency: {F[-1]:.2f} MHz (target 105 MHz after the reference step)")

fig, axs = plt.subplots(3, 1, figsize=(8, 8), sharex=True)
axs[0].plot(T, F);  axs[0].set_ylabel("VCO freq (MHz)")
axs[0].axhline(100, ls=":", c="gray"); axs[0].axhline(105, ls=":", c="gray")
axs[1].plot(T, VC); axs[1].set_ylabel("Vctrl (V)")
axs[2].plot(T, E);  axs[2].set_ylabel("Phase error (ns)"); axs[2].set_ylim(-10, 10)
for x, lab in [(30, "ref 10 -> 10.5 MHz"), (50, "+20 mV disturbance"), (55, "removed")]:
    for a in axs: a.axvline(x, ls="--", c="red", alpha=0.4)
axs[0].text(30.5, 91, "ref 10 -> 10.5 MHz", color="red", fontsize=8)
axs[0].text(50.5, 91, "+20 mV", color="red", fontsize=8)
axs[2].set_xlabel("Time (us)")
for a in axs: a.grid(True)
fig.suptitle("PLL lock acquisition, reference step and disturbance")
fig.tight_layout(); fig.savefig("plots/sim_lock.png", dpi=150)

# %% Cross-check: lock time vs loop bandwidth from simulation (no events)
fns = [100e3, 200e3, 356e3, 600e3, 1e6]
sim_lock = []
for fn in fns:
    t_, vc_, f_, e_ = simulate(fn=fn, t_end=40e-6, events=False)
    # lock time = first time frequency stays within +/-1 % of the 100 MHz target
    inside = np.abs(f_ - 100.0) < 1.0
    idx = np.where(~inside)[0]
    sim_lock.append(t_[idx[-1]+1] if len(idx) else 0.0)
print("\nfn (kHz) | simulated settle to +/-1 MHz (us)")
for fn, s in zip(fns, sim_lock):
    print(f"{fn/1e3:8.0f} | {s:8.2f}")

fig, ax = plt.subplots(figsize=(7, 4))
ax.loglog(np.array(fns)/1e3, sim_lock, "o-")
ax.set_xlabel("Natural frequency fn (kHz)"); ax.set_ylabel("Settling time (us)")
ax.set_title("Simulated lock time vs loop bandwidth (start at 90 MHz)")
ax.grid(True, which="both"); fig.tight_layout()
fig.savefig("plots/sim_locktime_vs_bw.png", dpi=150)

if not os.environ.get("NO_DISPLAY"):
    plt.show()
