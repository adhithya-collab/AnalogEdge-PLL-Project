// =====================================================================
// AnalogEdge - PLL Behavioral Model (design.sv)
// Blocks: PFD -> Charge Pump + Loop Filter + VCO -> Divide-by-N
// Target: fref = 10 MHz, N = 10, fout = 100 MHz
// Run on EDA Playground (SystemVerilog, Riviera-PRO or Xcelium)
// =====================================================================
`timescale 1ns/1ps

// ---------------------------------------------------------------------
// Phase-Frequency Detector (tri-state, no dead zone)
// ---------------------------------------------------------------------
module pfd (
  input  clk_ref,
  input  fb,
  output reg up,
  output reg dn
);
  wire #0.2 rst = up & dn;          // reset pulse after both go high
  initial begin up = 0; dn = 0; end
  always @(posedge clk_ref or posedge rst) if (rst) up <= 0; else up <= 1;
  always @(posedge fb      or posedge rst) if (rst) dn <= 0; else dn <= 1;
endmodule

// ---------------------------------------------------------------------
// Charge pump + 2nd-order passive loop filter (R in series with C) + VCO
//
//  - Charge pump: +ICP while UP, -ICP while DN, 0 otherwise.
//  - Capacitor voltage vc is integrated exactly at every UP/DN event.
//  - VCO phase (in cycles) = integral of f(vc) dt + KVCO*R*C*(vc - VINIT).
//    The second term is the exact effect of the R*Icp proportional path,
//    because the charge delivered is Q = C*(vc - VINIT). This avoids
//    aliasing the very short charge pump pulses.
//  - vdist is a disturbance voltage added to the VCO control (supply noise).
// ---------------------------------------------------------------------
module cp_lf_vco #(
  parameter real ICP   = 100e-6,   // charge pump current (A)
  parameter real R     = 6261.0,   // loop filter resistor (ohm)
  parameter real C     = 100e-12,  // loop filter capacitor (F)
  parameter real KVCO  = 50e6,     // VCO gain (Hz/V)
  parameter real F0    = 100e6,    // VCO centre frequency at VC0 (Hz)
  parameter real VC0   = 1.0,      // control voltage for F0 (V)
  parameter real VINIT = 0.8       // initial capacitor voltage (V) -> 90 MHz start
)(
  input  up,
  input  dn,
  output reg vco_clk
);
  localparam real TSTEP = 0.05;    // VCO update step (ns)

  real vc, fvco, icp_now, t_last, ph_int, phi, vdist;

  initial begin
    vc = VINIT; fvco = F0 + KVCO*(VINIT-VC0);
    icp_now = 0.0; t_last = 0.0; ph_int = 0.0; phi = 0.0;
    vdist = 0.0; vco_clk = 0;
  end

  // Advance capacitor voltage and VCO phase up to the current time
  task update_filter;
    real tnow, dt_s, vc_old, vc_avg;
    begin
      tnow   = $realtime;                       // ns
      dt_s   = (tnow - t_last) * 1e-9;
      vc_old = vc;
      vc     = vc + icp_now * dt_s / C;
      if (vc < 0.0) vc = 0.0;
      if (vc > 2.0) vc = 2.0;
      vc_avg = 0.5 * (vc_old + vc);
      ph_int = ph_int + (F0 + KVCO*(vc_avg + vdist - VC0)) * dt_s;
      t_last = tnow;
      fvco   = F0 + KVCO*(vc + vdist - VC0);
      phi    = ph_int + KVCO*R*C*(vc - VINIT);
    end
  endtask

  // Charge pump state changes on every UP/DN edge
  always @(up or dn) begin
    update_filter();
    if (up && !dn)      icp_now =  ICP;
    else if (dn && !up) icp_now = -ICP;
    else                icp_now =  0.0;
  end

  // VCO output clock, regenerated every TSTEP
  always #(TSTEP) begin
    update_filter();
    vco_clk = ((phi - $floor(phi)) < 0.5);
  end
endmodule

// ---------------------------------------------------------------------
// Divide-by-N feedback divider
// ---------------------------------------------------------------------
module divider #(parameter integer N = 10)(
  input  clk_in,
  output clk_out
);
  integer cnt;
  initial cnt = 0;
  always @(posedge clk_in) begin
    if (cnt == N-1) cnt <= 0; else cnt <= cnt + 1;
  end
  assign clk_out = (cnt < N/2);     // rising edge when cnt wraps to 0
endmodule
