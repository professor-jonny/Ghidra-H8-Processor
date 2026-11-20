# RVR X3 (21000011) injector pulse path - narrated

2026-11-21. Addresses are Ghidra addresses (file offset + 0x10000 for calibration, as used in the EcuFlash XML).
"Verified" = observed in disassembly and/or the three RVR EvoScan logs. "Inferred" = not checked.

## Units
- The pulse is in timer ticks of 4 us (verified: minimum pulse 5 x 64 ticks = 1.28 ms is exactly the lowest non-zero logged InjPulseWidth in 1075 samples).
- MUT InjPulseWidth = high byte of F970 (= 4 x pulse), so 0.256 ms per count (64 ticks x 4 us).

## The path, in order (fuel_pw_and_airvol_compute, 0x29fba)
1. Airflow/load term. A filtered airflow/load value is built from F1D8/F1DA/F1D2/F1DC and F1B6, slew-limited into F1D0 (inferred meaning; arithmetic verified).
2. Base fuel pulse (0x2a553). pulse = F268 x X / 0x200, then x F1D0 / 0x400, with X = hi(F26E) + F288 + F280 + 0x80 (fuel-cut-enable variant clamps between cal 0x8da and 0x8dc). F268 is written by f25a_f2xx_state_mirror_update (not traced). The injector scaling word (0x808) enters through the load chain (f28e_f292_knock_lambda_composite_calc multiplies by it); that chain is only partly traced.
3. Transient fuel (0x2a56b). Add F256 (accel enrichment), subtract F258 (decel), never to zero. F24E keeps this pulse (before the items below).
4. Low pulse width offset (injector_pw_add_latency_offsets, 0x2a7f7). If pulse < 0x209 (2.1 ms) add byte[pulse >> 3] from the table at 0x11df7 (66 bytes, 32 us per step, 175 = 0.70 ms falling to 0 at step 38 = 1.2 ms). Role inferred from the code; the same table follows the latency table in the EVO5 and VR4.
5. Battery latency (same function). Add F2CC. F2CC = F2CE x word@0x800 / 4, F2CE = table 0x11df0 looked up on battery voltage (axis 0x2d260, 0.0733 V per count). RVR word@0x800 = 15, so one table count = 15 us = 0.015 ms (verified against the logged InjectorLatency, 1019 of 1091 rows within 1.5 counts).
6. Minimum / maximum (0x2a67c-0x2a6a8). Clamp between R5 and 0xFDE8. R5 = word@0x804 << 6 = 320 ticks = 1.28 ms when F17A <= word@0x806 (255), else 0. Parameter order of clamp_u16 inferred; the 1.28 ms floor is verified in the logs.
7. Output values (0x2a6ad-0x2a6d7). F254/F250/F252 = pulse; F970 = 4 x pulse (MUT InjPulseWidth); F972 = 4 x pulse (MUT AirVol byte).
8. Which injectors (0x2a6db-0x2a718). Mode 1: channel mask from table 0x32a0 (0001,0004,0008,0002 = channels 1,3,4,2, firing order 1-3-4-2) indexed by F5EA, with table 0x329e (same list one entry back) ORed in when F31C bit6 is set and bit7 picks the table. Mode 2: all four (0xF). Mode 0: none.
9. Dispatch (channel_enable_mask_build_and_dispatch_ff2x_ff3x, 0x2a83b). mask &= 0xF & F514 & F3DC, and & F228 (if F1F2 bit6 and cal byte 0x2ca) and & F730 (if F1F4 bit2). multi_channel_reg_write_and_poll_ff2x_ff3x (0x16297) then sets each enabled channel's timer compare: on at counter + 2, off at counter + 2 + pulse. Every channel gets the same pulse: there is NO per-cylinder trim in this path (verified by reading the dispatcher).
10. Fuel accumulator (0x2a759). F336:F338 += (enabled injectors) x F24E, i.e. fuel pulse before latency/offset/minimum. Every 100 scheduler ticks tcu_rx_main_scheduler latches it to F33A/F33C and zeroes it. sci1_periodic_status_frame_build reports F33A:F33C x 0x246 / (word@0x808 << 8) as F552/F554, which is proportional to fuel volume (pulse x injector flow). The physical unit of that value is not worked out.

## Calibration words and tables found (XML address = Ghidra address)
| XML | What | RVR value | Status |
|---|---|---|---|
| 10800 | Injector latency base (us per latency count) | 15 (EVO5 24, VR4 15 at 10300) | verified |
| 10804 | Minimum pulse width, x0.256 ms | 5 (1.28 ms) | verified in logs |
| 10806 | Minimum pulse threshold on F17A | 255 (VR4 48) | code verified, meaning inferred |
| 10808 | Injector scaling (larger = smaller injector) | 69 (EVO5 54 at 10806) | verified use, cc/min constant not proven |
| 11df0 | Battery voltage latency table, 7 bytes | 255,165,89,53,31,15,4 | verified in logs |
| 11df7 | Low pulse width offset, 66 bytes | 175 ... 0 | inferred role |
| 132a0 / 1329e | Injector channel masks (not in XML) | 1,4,8,2 | verified from code |

## Open
- Constant in cc/min = K / x: K = 29241 (RVRbase) or 30240 is not proven. The log fit gives about 29,700 +/- 10%.
- Writer of F268 and the full airflow chain (F1D0) are not traced.
- RVR words at 0x802 (0x032D) and 0x80A (0x3D) are unidentified.
- Per-cycle fuel volume unit of F552/F554 not derived.
## Airflow to base fuel gain (traced 2026-11-21)

Where the 0x808 injector scale enters (f28e_f292_knock_lambda_composite_calc, 0x2351d):

1. F292 = MAF Scaling table (0x1800, axis MAF Hz) + word@0x818
2. F294 = Barometric Pressure Compensation 3D table (0x1840)
3. F296 = o2_lambda_correction_apply()
4. F290 = F292 x F294 x F296 / 0x4000
5. F28E = F290 x (indexed byte) x word@0x808 / 0x400   <-- injector scaling enters here
6. f266_knock_octane_composite_trim_compute: F266 = F28E x F29A x (F2B6, F2C8/F2CA, F2BE, F482 trims, gated by flags 0x31e/0x309/0x30a) x table entry
7. f25a_f2xx_state_mirror_update: F268 = F266
8. fuel_pw_and_airvol_compute: base pulse = F268 x (F26E.. sum) / 0x200 x F1D0 / 0x400

Other findings:
- F29A = coolant-derived factor: F130 (F12E, or 0xCD when invalid) x 0xA0 (fixed point 8). Written by coolant_temp_validity_and_scale.
- F29C = throttle_target_ramp_update output, clamp_u8 around 0x80 (1.0); uses post-start enrich RPM axis and tables 0x1d98, 0x1d86.
- F1E0 (maf_freq_raw) = F1B6 x 0x401a / F5E0, F5E0 written by the ch2/ch4 input-capture ISR. F1B6 is only written by table_select_scale_fanout_f1be_f1c2 and fueling_openloop_output_copy.
- Composite tables 11f1a, 11e8a, 11e98, 11f40, 11f4e, 11f34, 11eda, 11ee6, 11ecc feed F2E0..F2EE and F310..F316 (same F28E x F29A inputs).
- No xrefs found: 11ea4, 12aee, 12d04, 12df9, 12e51, 13270, 13282.
- Unverified: what the indexed byte (read_indexed_byte_f1fc) is, and the physical meaning of F28E.

## Correction: where airflow enters (2026-11-21, later trace)

- F1B6 is measured engine load per event, built in fuel_pw_and_airvol_compute: F1D2 (counter difference from F992, via sci1_timing_period_tracker) x 0x9C, blended, clamped to F1C0 below and F1BE above, set to 0 when F25A bit 1 is set.
- F1D0 = F1B6 x F29C (F1C4), rate limited with words 0x95E/0x960/0x962 and capped by F2E4. This is the airflow term in the pulse. Earlier note calling F1D0 a gain constant was wrong.
- F1E0 = F1B6 x 0x401A / F5E0 turns that load back into a frequency using the captured period F5E0.
- Tables 11870 / 11884 are the upper limit on F1B6 (Load Limit vs RPM), not base fuel.
- Logs: pulse x RPM / 1000 = 0.0696 x AirFlow - 1.0, R2 0.94, n = 1020, which fits pulse proportional to load.
- Table 11804 (MAF Scaling, 0x65..0xB0) only supplies a weak correction (F292), not the main airflow dependence.

## Other tables named on 2026-11-21 (ECU 21000011)

All names below are inferred from code and are recorded in the XML comments with function names and addresses.

- ISC (idle) group: F342 is the sum of correction terms (F344, F352 to F35C, F36A to F374 and others) around a 0x8000 bias, clamped between table 12cf8 (or 10) and 0x46. The F356 term takes the 127dc air-temp trim when load F18E is above table 127f2 (RPM axis). F402 is the stepper target; F4AC is a throttle threshold compared with TPS (not a purge duty).
- EGR duty tables (12df9, 12e51, 12ea6, 12eb2) and the O2 heater duty correction (12dda) are named from egr_duty_target_calc and the F4DC adder.
- Composite corrections: F2EA = F28E * 11f40 * F29A / 0x4000 * (11f4e * 11f34) / 0x800; F314 = clamp(11eda base, scaled when F20E bit13 is set, + 11ee6); F2E6, F2EC and F316 come straight from 11e8a, 11e98 and 11ecc. 11f1a sets F20E bit13 from the zone dwell counter EF6A.
- Trailing-time counters: 11daa (F2A0, F2C6) and 11db8 (F2A2, F2C0, F2C2, F2C4) are loaded from engine temp and decay on timers EFBA/EFBC. F2C8*2+0x80 is a multiplier in the O2 mode 7/8 correction (3D table 11dc9). 11db8 is a duplicate XML entry (also named Lean Spool Trailing Time - Rich Side).
- Thresholds: 12870 (F33E condition vs F18E), 12aee (F186 pulse width), 12ed2 to 12efc (four tier tables, all 0xFF, so disabled).
- Unreferenced: 12d04 and 13270 have no code references; 11cee is only reached through a pointer array with no identified reader.

## TCU link (found by reading the W4A51 program 21451005)

- The ECU and TCU exchange frames over SCI3. The ECU sends 7 bytes: TPS low byte, F17A low byte (engine speed / 8), status flags (diagnostic_status_f4b4_build), injector pulse F18C (or F196 scaled), a config nibble, a comms-lost flag 0x40, then a checksum. The TCU sends 4 data bytes (3 zeros and a fault-index nibble) plus a checksum.
- No torque-reduction request is sent by this ECU ROM. F4BC (TCU byte 0) is 0 while the TCU answers and 0x80 after 50 missed frames; it feeds the F4AC threshold offset.
- The P1DR bit 6/7 outputs (F0EA bits 2 and 3) only run when F1F2 bit13 is set, which is clear in both ECU ROMs.

## Correction: F17A is engine speed / 8 (2026-11-21)

F17A = clamp_u8((F170 + 4) >> 3) with F170 = 0x1D4C00 / the RPM period value, so rpm = F17A * 31.25. All 1091 RPM samples in the three EvoScan logs are exact multiples of 31.25, and the VR4 minimum-pulse threshold word 48 equals 1500 rpm. Earlier notes, table names and the Ghidra name that called F17A a torque value or torque scale were wrong; in the ECU-to-TCU frame the second byte is engine speed / 8.
