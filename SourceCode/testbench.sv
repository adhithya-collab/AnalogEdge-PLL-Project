// =====================================================================
// AnalogEdge - PLL Testbench (testbench.sv)
// Scenario:
//   0 us   : start, VCO begins at 90 MHz (10 % frequency error) -> lock acquisition
//   30 us  : reference steps 10 MHz -> 10.5 MHz
//   50 us  : +20 mV disturbance on VCO control for 5 us (supply noise)
//   80 us  : end
// Prints LOCK/UNLOCK events, and CSV lines you can paste into Colab.
// =====================================================================
`timescale 1ns/1ps

module tb;
  localparam integer N = 10;

  real fref = 10.0e6;
  reg  clk_ref = 0;
  wire fb, vco_clk, up, dn;

  real t_ref = 0.0, t_fb = 0.0, perr = 0.0, Tref = 100.0, t_event = 0.0;
  real vctrl_mon = 0.0, fvco_mon = 0.0;
  integer good = 0;
  reg locked = 0;

  pfd           u_pfd (.clk_ref(clk_ref), .fb(fb), .up(up), .dn(dn));
  cp_lf_vco     u_vco (.up(up), .dn(dn), .vco_clk(vco_clk));
  divider #(N)  u_div (.clk_in(vco_clk), .clk_out(fb));

  // Reference clock (frequency can change during the run)
  always #(0.5e9/fref) clk_ref = ~clk_ref;

  // Phase error measurement and lock detector
  always @(posedge clk_ref) t_ref = $realtime;

  always @(posedge fb) begin
    t_fb = $realtime;
    Tref = 1.0e9 / fref;
    perr = t_fb - t_ref;
    if (perr >  Tref/2) perr = perr - Tref;
    if (perr < -Tref/2) perr = perr + Tref;

    if ((perr < 0 ? -perr : perr) < 0.3) good = good + 1;
    else begin
      good = 0;
      if (locked) begin
        locked = 0;
        $display("UNLOCK at t = %f us", $realtime/1000.0);
      end
    end

    if (good == 30 && !locked) begin
      locked = 1;
      $display("LOCK   at t = %f us  (lock time after last event = %f us)",
               $realtime/1000.0, ($realtime - t_event)/1000.0);
    end
  end

  // Waveform probes (sampled so EPWave stays light)
  always #20 begin
    vctrl_mon = u_vco.vc;
    fvco_mon  = u_vco.fvco/1e6;       // MHz
  end

  // CSV log: time_us, vc_V, fvco_MHz, phase_error_ns
  always #200 $display("CSV,%f,%f,%f,%f", $realtime/1000.0, u_vco.vc,
                       u_vco.fvco/1e6, perr);

  // Stimulus
  initial begin
    $dumpfile("dump.vcd");
    $dumpvars(1, tb);

    #30000;
    fref = 10.5e6;  t_event = $realtime;
    $display("EVENT at 30 us: reference 10 MHz -> 10.5 MHz");

    #20000;
    u_vco.vdist = 0.02;  t_event = $realtime;
    $display("EVENT at 50 us: +20 mV disturbance on VCO control");

    #5000;
    u_vco.vdist = 0.0;
    $display("EVENT at 55 us: disturbance removed");

    #25000;
    $display("DONE");
    $finish;
  end
endmodule
