# =====================================================================
# AnalogEdge - PLL linear model, lock-time and jitter sweeps
# Works in Google Colab or any Python with numpy, scipy, matplotlib.
# Type-II charge-pump PLL, 2nd-order passive loop filter (R + C).
# =====================================================================
# %% Parameters
import os
import numpy as np
import matplotlib
matplotlib.use("Agg") if os.environ.get("NO_DISPLAY") else None
import matplotlib.pyplot as plt
from scipy import signal

# numpy 2.x renamed trapz -> trapezoid; support both (Colab may have either)
_trapz = getattr(np, "trapezoid", None) or np.trapz

FREF  = 10e6                 # reference frequency (Hz)
N     = 10                   # divider
FOUT  = FREF * N             # 100 MHz
ICP   = 100e-6               # charge pump current (A)
KVCO  = 2*np.pi*50e6         # 50 MHz/V in rad/s/V
ZETA0 = 0.7
FN0   = None                 # computed below from C = 100 pF

C0    = 100e-12
WN0   = np.sqrt(ICP*KVCO/(2*np.pi*N*C0))
FN0   = WN0/(2*np.pi)
R0    = 2*ZETA0/(WN0*C0)
print(f"Baseline design: fn = {FN0/1e3:.0f} kHz, zeta = {ZETA0}, R = {R0:.0f} ohm, C = 100 pF")

os.makedirs("plots", exist_ok=True)

# %% Helper functions
def design(fn, zeta):
    """Return R, C that give natural frequency fn and damping zeta."""
    wn = 2*np.pi*fn
    C = ICP*KVCO/(2*np.pi*N*wn**2)
    R = 2*zeta/(wn*C)
    return R, C

def closed_loop(fn, zeta):
    wn = 2*np.pi*fn
    return signal.TransferFunction([2*zeta*wn, wn**2], [1, 2*zeta*wn, wn**2])

def step_metrics(fn, zeta, band=0.01):
    """Settling time (to +/-1 %) and overshoot of the frequency-step response."""
    sys = closed_loop(fn, zeta)
    t = np.linspace(0, 40/(2*np.pi*fn), 20000)
    t, y = signal.step(sys, T=t)
    overshoot = max(0.0, (y.max()-1.0)*100)
    outside = np.where(np.abs(y-1.0) > band)[0]
    ts = t[outside[-1]] if len(outside) else 0.0
    return ts, overshoot

def phase_margin(fn, zeta):
    R, C = design(fn, zeta)
    f = np.logspace(3, 8, 20000)
    s = 2j*np.pi*f
    G = (ICP/(2*np.pi)) * (R + 1/(s*C)) * (KVCO/s) / N
    mag = np.abs(G)
    i = np.where(mag < 1)[0][0]
    return f[i], 180 + np.degrees(np.angle(G[i]))

def rms_jitter(fn, zeta, Lref_dBc=-130.0, Lvco_dBc_1M=-110.0):
    """Output RMS jitter (s) from white reference noise and 1/f^2 VCO noise."""
    f = np.logspace(3, np.log10(FREF/2), 4000)
    s = 2j*np.pi*f
    wn = 2*np.pi*fn
    H = (2*zeta*wn*s + wn**2) / (s**2 + 2*zeta*wn*s + wn**2)
    S_ref = 2*10**(Lref_dBc/10) * np.ones_like(f)            # rad^2/Hz at input
    S_vco = 2*10**(Lvco_dBc_1M/10) * (1e6/f)**2              # rad^2/Hz at output
    out_ref = N**2 * np.abs(H)**2 * S_ref                    # ref noise, low-pass
    out_vco = np.abs(1-H)**2 * S_vco                         # VCO noise, high-pass
    var_ref = _trapz(out_ref, f)
    var_vco = _trapz(out_vco, f)
    k = 1/(2*np.pi*FOUT)
    return (np.sqrt(var_ref)*k, np.sqrt(var_vco)*k,
            np.sqrt(var_ref+var_vco)*k)

# %% Sweep 1: frequency-step response for different loop bandwidths
fig, ax = plt.subplots(figsize=(7, 4))
for fn in [100e3, 356e3, 1e6]:
    sys = closed_loop(fn, ZETA0)
    t = np.linspace(0, 12e-6, 3000)
    t, y = signal.step(sys, T=t)
    ax.plot(t*1e6, y, label=f"fn = {fn/1e3:.0f} kHz")
ax.axhline(1.01, ls=":", c="gray"); ax.axhline(0.99, ls=":", c="gray")
ax.set_xlabel("Time (us)"); ax.set_ylabel("Normalised response")
ax.set_title("Closed-loop step response (zeta = 0.7)")
ax.legend(); ax.grid(True)
fig.tight_layout(); fig.savefig("plots/step_response.png", dpi=150)

# %% Sweep 2: lock time vs loop bandwidth (zeta = 0.7)
fns = np.logspace(np.log10(50e3), np.log10(2e6), 40)
ts  = np.array([step_metrics(fn, ZETA0)[0] for fn in fns])
fig, ax = plt.subplots(figsize=(7, 4))
ax.loglog(fns/1e3, ts*1e6, "o-")
ax.set_xlabel("Natural frequency fn (kHz)"); ax.set_ylabel("Settling time to 1 % (us)")
ax.set_title("Lock time vs loop bandwidth (zeta = 0.7)"); ax.grid(True, which="both")
fig.tight_layout(); fig.savefig("plots/locktime_vs_bw.png", dpi=150)

# %% Sweep 3: damping sweep -> overshoot, settling time, phase margin
zetas = np.linspace(0.3, 1.5, 25)
ov  = [step_metrics(FN0, z)[1] for z in zetas]
tsz = [step_metrics(FN0, z)[0]*1e6 for z in zetas]
pm  = [phase_margin(FN0, z)[1] for z in zetas]
fig, axs = plt.subplots(1, 3, figsize=(13, 3.8))
axs[0].plot(zetas, ov, "o-");  axs[0].set_title("Overshoot (%)")
axs[1].plot(zetas, tsz, "o-"); axs[1].set_title("Settling time (us)")
axs[2].plot(zetas, pm, "o-");  axs[2].set_title("Phase margin (deg)")
for a in axs: a.set_xlabel("Damping factor zeta"); a.grid(True)
fig.tight_layout(); fig.savefig("plots/damping_sweep.png", dpi=150)

# %% Sweep 4: RMS jitter vs loop bandwidth
jr, jv, jt = zip(*[rms_jitter(fn, ZETA0) for fn in fns])
fig, ax = plt.subplots(figsize=(7, 4))
ax.loglog(fns/1e3, np.array(jt)*1e12, "k-o", label="Total")
ax.loglog(fns/1e3, np.array(jr)*1e12, "--", label="Reference noise")
ax.loglog(fns/1e3, np.array(jv)*1e12, "--", label="VCO noise")
ax.set_xlabel("Natural frequency fn (kHz)"); ax.set_ylabel("RMS jitter (ps)")
ax.set_title("Output jitter vs loop bandwidth (zeta = 0.7)")
ax.legend(); ax.grid(True, which="both")
fig.tight_layout(); fig.savefig("plots/jitter_vs_bw.png", dpi=150)

best = int(np.argmin(jt))
print(f"Jitter-optimal fn ~ {fns[best]/1e3:.0f} kHz, total RMS jitter ~ {jt[best]*1e12:.2f} ps")

# %% Summary table for the report
print("\nfn (kHz) | settle 1% (us) | overshoot (%) | PM (deg) | jitter (ps)")
for fn in [100e3, 200e3, FN0, 600e3, 1e6]:
    t_s, o = step_metrics(fn, ZETA0)
    _, p = phase_margin(fn, ZETA0)
    print(f"{fn/1e3:8.0f} | {t_s*1e6:14.2f} | {o:13.1f} | {p:8.1f} | {rms_jitter(fn, ZETA0)[2]*1e12:.2f}")

if not os.environ.get("NO_DISPLAY"):
    plt.show()
