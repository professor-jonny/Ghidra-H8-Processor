Cross-Binary Matched Functions -- Evo 5 Stock Prototype/Cleanup Checklist
===========================================================================

Generated 2026-07-23 from ghidra:bulk_fuzzy_match (source=4g63t md352553,
target=22580006_EVO5_Stock.hex, threshold=0.9). Companion to functions.md
(the w4a51 checklist) -- same purpose, different target ROM.

This ROM matched noticeably BETTER than w4a51 did: almost the entire named
4g63t function set (721 functions) came back at 0.9+, with the large
majority at a perfect 1.0 (byte-identical). Below is the 1:1 (score==1.0)
subset only -- the highest-confidence group, safe to rename/prototype
immediately. Near-1.0 matches (0.92-0.99) and known collisions are listed
separately below the 1:1 list; see functions.md for the cleanup method
already applied to all of these on the 4g63t side.

IMPORTANT -- WORK TARGET: This list identifies functions COMMON between
4g63t and Evo5 (i.e. confirms the match/naming is valid across both ROMs).
All actual rename/prototype/cleanup work is done ONLY on the 4g63t (RVR,
md352553.hex) source ROM, which is the maintained reference base. The Evo5
ROM (22580006_EVO5_Stock.hex) is NEVER opened or modified -- it exists
purely as a second data point to confirm cross-ROM function identity for
a future FID database / fuzzy-matching script. Do not ask to open or edit
Evo5 again; this is settled.

Columns: [ ] = not yet confirmed/cleaned up on the 4g63t side for this
entry, [x] = done. Address pairs are 4g63t (source) -> Evo5 (target,
reference only, not edited). Prototypes/types are applied on the 4g63t
address only.

Score 1.0 matches (267 total)
-----------------------------------------------------------------------
- [x] sat_add_u16                              0x00014000 -> 0x00014000
- [x] sat_add_s16                              0x0001401f -> 0x0001401f
- [x] sat_sub_u16                              0x00014036 -> 0x00014036
- [x] sat_sub_u16_clamp0                       0x00014045 -> 0x00014045
- [x] sat_mul_u16                              0x0001405c -> 0x0001405c
- [x] mul_u16_hi                               0x0001406f -> 0x0001406f
- [x] div_u16_sat                              0x000140c0 -> 0x000140c0
- [x] div_u32_u16_sat                          0x000140dc -> 0x000140dc
- [x] div_u16_rounded                          0x0001412b -> 0x0001412b
- [x] div_s32_s16_rounded                      0x00014151 -> 0x00014151
- [x] div_u32_u16_rounded                      0x0001417d -> 0x0001417d
- [x] muldiv_u16                               0x000141ba -> 0x000141ba
- [x] muldiv_u16_scaled                        0x000141dc -> 0x000141dc
- [x] muldiv_s16_rounded                       0x00014219 -> 0x00014219
- [x] muldiv_s16_rounded_3op                   0x00014247 -> 0x00014247
- [x] mul_u16_x2_sat_alt                       0x00014293 -> 0x00014293
- [x] mul_u16_sat_s16                          0x000142b4 -> 0x000142b4
- [x] mul_u16_x2_sat                           0x000142f3 -> 0x000142f3
- [x] mul_u16_shr8_sat                         0x0001436c -> 0x0001436c
- [x] muldiv_u16_shr8_sat                      0x00014387 -> 0x00014387
- [x] mul_fixedpoint_8                         0x000143bf -> 0x000143bf
- [x] clamp_u8                                 0x0001442d -> 0x0001442d
- [x] passthrough_or_sat                       0x0001443c -> 0x0001443c
- [x] clamp_u16                                0x0001444c -> 0x0001444c
- [x] select_min_xy_triple                     0x00014471 -> 0x00014471  (FIXED -- median-of-three selector on 32-bit hi:lo pairs, fully traced and bound: select_min_xy_triple(hi_a,lo_a,hi_b,lo_b,hi_c,lo_c) -> ushort, see plate comment)
- [x] get_high_byte                            0x000144b4 -> 0x000144b4
- [x] identity_passthrough_u16                 0x000144bf -> 0x000144bf
- [x] shift_left_byte_to_high                  0x000144c6 -> 0x000144c6
- [x] identity_passthrough_arg1                0x000144d1 -> 0x000144d1
- [x] round_high_byte_signed                   0x000144da -> 0x000144da
- [x] inc_if_signed_flag                       0x000144ef -> 0x000144ef
- [x] swap_invert_high_byte                    0x0001450b -> 0x0001450b
- [x] zero_ram_range                           0x0001451a -> 0x0001451a
- [x] decrement_counters_in_range              0x0001452d -> 0x0001452d
- [x] increment_counters_in_range              0x0001454c -> 0x0001454c
- [x] axis_interp_lerp_u8frac_256              0x0001456d -> 0x0001456d
- [x] weighted_blend_u8frac                    0x00014599 -> 0x00014599
- [x] weighted_blend_4term_u8frac              0x000145c5 -> 0x000145c5
- [x] axis_lookup_interp                       0x00014735 -> 0x00014735
- [x] axis_interp_lerp_u8frac                  0x000147c6 -> 0x000147c6
- [x] read_indexed_byte_f1fc                   0x0001481c -> 0x0001481c
- [x] table_read_indexed                       0x00014880 -> 0x00014880
- [x] stub_empty_0x1519e                       0x0001519e -> 0x0001519e
- [x] update_flag_f9a0_bit6_cond                0x00015319 -> 0x00015319
- [x] compose_status_words_f0f6_fc              0x00015341 -> 0x00015341
- [x] check_flag_fe96_bit7_clear                0x0001553d -> 0x0001553d
- [x] check_flag_f0d8_bit0_clear                0x00015549 -> 0x00015549
- [x] check_flag_fe87_bit1_clear                0x00015555 -> 0x00015555
- [x] check_flag_fe8a_bit1_set                  0x00015561 -> 0x00015561
- [x] zero_var_f15a                            0x000156c2 -> 0x000156c2
- [x] identity_passthrough_u16_b               0x000156c8 -> 0x000156c8
- [x] mirror_status_f0e6_to_ports              0x000156ce -> 0x000156ce
- [x] update_flag_fe97_bit2_cond                0x00015857 -> 0x00015857
- [x] update_flag_fe82_bit2_cond                0x00015877 -> 0x00015877
- [x] toggle_flag_fe8b_bit4                    0x00015897 -> 0x00015897
- [x] clear_flag_fe93_bit4                     0x0001589d -> 0x0001589d
- [x] update_port_fe82_indexed                 0x000158a7 -> 0x000158a7
- [x] software_pwm_output_scheduler            0x000158d7 -> 0x000158d7
- [x] init_scale_factor_f9ac                   0x00015a3a -> 0x00015a3a
- [x] peripheral_regs_ff2x_ff9x_bulk_zero_init 0x00015a76 -> 0x00015a76
- [x] init_reg_feb8_feb9                       0x00015aff -> 0x00015aff
- [x] adc_channel_convert_and_read             0x00015b0d -> 0x00015b0d
- [x] init_flags_ff51_52                       0x00015b90 -> 0x00015b90
- [x] detect_sci1_param_change_reset           0x00015c6c -> 0x00015c6c
- [x] timer_block_cold_init_b                  0x00015d36 -> 0x00015d36
- [x] timer_ff41_ff44_ff4a_cold_init           0x00015dd0 -> 0x00015dd0
- [x] timer_ff41_ff42_warm_init                0x00015e01 -> 0x00015e01
- [x] sci3_timeout_set_abort                   0x00015e17 -> 0x00015e17
- [x] sci3_timeout_clear_flag                  0x00015edb -> 0x00015edb
- [x] timer_ff44_ff4a_arm_channels_atomic      0x00015f1a -> 0x00015f1a
- [x] timer4_oc_arm_from_flags                 0x00015f71 -> 0x00015f71
- [x] compose_status_bits_fe86_fe8a            0x00016029 -> 0x00016029
- [x] peripheral_block_ff15_cold_init          0x00016059 -> 0x00016059
- [x] peripheral_block_ff15_warm_init          0x0001609d -> 0x0001609d
- [x] isr_nmi                                  0x000160d9 -> 0x000160d9
- [x] peripheral_reg_ff1d_cold_init            0x00016102 -> 0x00016102
- [x] latch_flag_read_fede_bit1                0x00016110 -> 0x00016110
- [x] latch_flag_read_fede_bit3                0x00016140 -> 0x00016140
- [x] propagate_flag_fe96_to_f0d8_db           0x0001615c -> 0x0001615c
- [x] peripheral_block_ff90_cold_init          0x000161ba -> 0x000161ba
- [x] scale_counter_ff96_to_byte_clamped       0x000161e6 -> 0x000161e6
- [x] init_state_block_ff21                    0x00016222 -> 0x00016222
- [x] peripheral_block_ff21_warm_init          0x0001626c -> 0x0001626c
- [x] multi_channel_reg_write_and_poll_ff2x_ff3x 0x00016297 -> 0x00016297
- [x] compose_fe86_fe8a_status_nibble          0x00016410 -> 0x00016410
- [x] timer_ff51_ff54_arm_init                 0x0001643a -> 0x0001643a
- [x] timer_ff51_ff52_disarm                   0x0001645e -> 0x0001645e
- [x] init_state_block_ff54                    0x0001646c -> 0x0001646c
- [x] timer_ff5a_set_clamped_armed             0x00016488 -> 0x00016488
- [x] serial_fef4_cold_init                    0x000164b7 -> 0x000164ce
- [x] serial_fef4_warm_init                    0x000164da -> 0x000164f1
- [x] serial_fef1_set_clamped                  0x000164f8 -> 0x00016529
- [x] serial_fef5_set_clamped                  0x00016505 -> 0x00016529
- [x] serial_fef9_set_clamped                  0x00016512 -> 0x00016529
- [x] peripheral_block_fec0_fed0_cold_init     0x0001651f -> 0x00016536
- [x] peripheral_fec0_fed0_state_update        0x0001655a -> 0x00016571
- [x] serial_fec3_load_byte0_init              0x00016600 -> 0x00016617
- [x] serial_fec3_load_next_byte               0x00016631 -> 0x00016648
- [x] serial_fec5_byte_to_fifo                 0x00016680 -> 0x00016696
- [x] latch_request_f588                       0x000166cd -> 0x000166e3
- [x] sci1_tx_response_feeder                  0x000166d7 -> 0x000166ed
- [x] sci1_rx_frame_accumulator                0x00016716 -> 0x0001672c
- [x] isr_tpu5_tgi5b_sci1_tie_clear            0x00016865 -> 0x0001687b
- [x] init_state_sentinels_f5d2                0x00016890 -> 0x000168a6
- [x] peripheral_ff42_ff62_enable              0x000168d9 -> 0x000168ef
- [x] flag_read_ff43_bit0_inverted              0x00016a97 -> 0x00015549  (collides w/ check_flag_f0d8_bit0_clear target -- RESOLVED, confirmed genuinely different, already typed bool(void))
- [x] peripheral_block_ff70_ff88_cold_init     0x00016aa3 -> 0x00016ab9
- [x] peripheral_block_ff70_ff88_warm_init     0x00016b83 -> 0x00016b99
- [x] f978_read_and_clear                      0x00016c09 -> 0x00016c1f
- [x] f978_increment_on_ff73_bit0              0x00016c13 -> 0x00016c29
- [x] ff88_set_scaled_clamped                  0x00016c33 -> 0x00016c49
- [x] isr_tpu3_tgi3a                           0x00016c4f -> 0x00016c65
- [x] pwm_ch0_period_track_update              0x00016d40 -> 0x00016d56
- [x] pwm_ch1_period_track_update              0x00016e1c -> 0x00016e32
- [x] f9a0_read_clear_bit4_atomic              0x00016f3b -> 0x00016f51
- [x] ff0d_clear_bits5_6                       0x00017154 -> 0x00017174
- [x] adc_sensor_convert_multi                 0x00017160 -> 0x00017180
- [x] adc_sensor_convert_single                0x000171c3 -> 0x000171e3  (RequestID param arrives in R1, not stack -- documented in plate comment, same class as adc_channel_convert_and_read/boot_ram_block_copy)
- [x] byte_sum_banked                          0x00017206 -> 0x00017226
- [x] sum_byte_array                           0x0001722b -> 0x0001724b
- [x] memcpy_banked                            0x00017256 -> 0x00017276
- [x] engine_mode_f20e_f510_check              0x000174a1 -> 0x000174a1
- [x] knock_condition_eval                     0x000174d4 -> 0x000174d4
- [x] isc_decel_fuel_cut_check                 0x0001792f -> 0x0001792f
- [x] isc_f03e_f45a_timer_update               0x0001799f -> 0x0001799f
- [x] isc_dashpot_override_check               0x0001842b -> 0x0001842b  (FIXED -- __stdcall_far root cause, resolved. Param: base_value)
- [x] engine_mode_f512_bit4_check              0x000185de -> 0x000185de
- [x] egr_activity_condition_check             0x00018628 -> 0x00018628
- [x] egr_coolant_rpm_enable_check             0x00018689 -> 0x00018689
- [x] egr_f490_condition_flags_update           0x000189c0 -> 0x000189c0  (raw stack0xfffe+6 read flagged in plate comment for manual review)
- [x] check_hysteresis_gate_f490               0x00018a55 -> 0x00018a55
- [x] check_mode_gate_f510                     0x00018ae5 -> 0x00018ae5
- [x] egr_f490_gear_transition_update           0x00018b17 -> 0x00018b17  (FIXED -- __stdcall_far root cause, resolved. Param: gear_bits)
- [x] egr_f0e6_valve_bits_update                0x00018b63 -> 0x00018b63
- [x] ign_advance_enable_flags_f440_update      0x00018e93 -> 0x00018e93
- [x] rpm_map_zone_flags_f43e_update            0x000191f0 -> 0x00019270
- [x] rpm_zone_enable_check                    0x000192ac -> 0x0001932c
- [x] o2_heater_timer_f088_update               0x00019b2a -> 0x00019a4a
- [x] o2_heater_iat_zone_select_f4f0            0x00019b5e -> 0x00019a7e
- [x] o2_heater_soak_enable_check               0x00019d0e -> 0x00019c2e
- [x] o2_heater_force_off_check                 0x00019d4b -> 0x00019c6b
- [x] o2_lambda_or_passthrough_select           0x00019f35 -> 0x00019fb5  (FIXED -- same __stdcall_far root cause as update_max, resolved. Params: _unused_far_pad, raw_value)
- [x] o2_wideband_mode_zero_check               0x00019f77 -> 0x00019ff7  (FIXED -- __stdcall_far root cause, resolved)
- [x] o2_wideband_midpoint_select               0x00019ff2 -> 0x0001a072  (FIXED -- __stdcall_far root cause, resolved)
- [x] o2_wideband_lsu_mode_check                0x0001a0a7 -> 0x0001a127
- [x] o2_mode11_lambda_select                   0x0001a130 -> 0x0001a1b0  (FIXED -- __stdcall_far root cause, resolved)
- [x] o2_closed_loop_config_check               0x0001a15c -> 0x0001a1dc
- [x] o2_sensor2_mode3_midpoint                 0x0001a1b9 -> 0x0001a239  (FIXED -- __stdcall_far root cause, resolved)
- [x] o2_downstream_type34_check                0x0001a1cc -> 0x0001a24c
- [x] o2_downstream_clamp_by_type               0x0001a1e5 -> 0x0001a265  (FIXED -- __stdcall_far root cause, resolved)
- [x] o2_wideband_mode82_check                  0x0001a205 -> 0x0001a285  (already clean)
- [x] o2_sensor2_mode20_select                  0x0001a212 -> 0x0001a292  (FIXED -- __stdcall_far root cause, resolved; confirmed genuinely different from o2_downstream_mode20_select despite Evo5 collision)
- [x] o2_downstream_mode20_select                0x0001a228 -> 0x0001a292  (FIXED -- __stdcall_far root cause, resolved; see collision note above)
- [x] o2_downstream_mode21_select                0x0001a23e -> 0x0001a2be  (FIXED -- __stdcall_far root cause, resolved)
- [x] o2_config4_mode16_check                   0x0001a254 -> 0x0001a2d4  (already clean)
- [x] o2_downstream_mode17_check                 0x0001a261 -> 0x0001a2e1  (already clean)
- [x] o2_downstream_mode64_select                0x0001a2a4 -> 0x0001a324  (FIXED -- __stdcall_far root cause, resolved)
- [x] o2_downstream_mode66_select                0x0001a2ba -> 0x0001a33a  (FIXED -- __stdcall_far root cause, resolved)
- [x] o2_downstream_mode48_select                0x0001a2e6 -> 0x0001a366  (FIXED -- __stdcall_far root cause, resolved)
- [x] status_flags_f202_build                    0x0001a31a -> 0x0001a41a
- [x] dtc_status_flags_f204_f206_build           0x0001a36f -> 0x0001a46f
- [x] boot_ram_block_copy                        0x00020024 -> 0x00020024
- [x] boot_sci1_init                             0x00020048 -> 0x00020048
- [ ] sci1_boot_security_seed_check              0x000201c0 -> 0x000201c0  (SKIPPED -- messy boot fn, spacebase warnings + unreachable blocks + infinite tail loop, see plate comment)
- [ ] sci1_boot_checksum_accumulate               0x000202b2 -> 0x000202b2  (SKIPPED -- real R4/R5 register-passed pointer params, same class as adc_channel_convert_and_read/boot_ram_block_copy)
- [x] sci1_tx_byte_blocking                       0x00020379 -> 0x00020379
- [ ] sci1_boot_rxbuf_write                      0x0002039f -> 0x0002039f  (SKIPPED -- messy recursive/register-reuse decompile, mismatched self-call arg counts, not worth forcing a prototype)
- [x] sci1_boot_rxbuf_read                       0x000203bd -> 0x000203bd
- [x] sci1_boot_build_data_frame                 0x000205a7 -> 0x000205a7
- [x] sci1_boot_build_eof_frame                  0x00020646 -> 0x00020646
- [x] flash_byte_program_verify                  0x000208c6 -> 0x000208c6
- [x] flash_timing_delay                        0x00020910 -> 0x00020910
- [x] flash_erase_sector_loop                    0x0002093c -> 0x0002093c
- [x] init_ee82_ee8a_from_rom_const              0x00020e00 -> 0x00020e00
- [x] cond_reset_and_latch_f10e_f118_prev        0x00020fb1 -> 0x00020fb1
- [x] fuel_cut_rpm_offset_select                 0x000211a1 -> 0x000211cb  (FIXED -- __stdcall_far root cause, resolved. Params: flags, base_value)
- [x] coolant_temp_range_check                   0x0002144b -> 0x00021475
- [x] idle_closed_loop_ready_check               0x000215c8 -> 0x000215ec
- [x] throttle_ramp_enable_check                 0x000217b6 -> 0x000217da
- [x] engine_torque_scale_state_reset             0x0002180b -> 0x0002183d
- [x] throttle_param_table_select                0x00021928 -> 0x0002195a
- [x] lambda_enable_inhibit_check                0x00021962 -> 0x00021994
- [x] fueling_openloop_output_copy               0x00021af3 -> 0x00021b25
- [x] fueling_inj_target_select                  0x00021b8f -> 0x00021bc1
- [x] inj_channel_state_init                     0x00021f00 -> 0x00021f80
- [x] ecu_openloop_state_reset                   0x00021f21 -> 0x00021fa1
- [x] control_state_latch_prev                   0x00021f70 -> 0x00021ff4
- [x] diag_flag_clear_and_param_reload           0x00021f92 -> 0x00022016
- [x] f1e6_hysteresis_gate_check                 0x00021fba -> 0x0002203e
- [x] rpm_load_window_condition_check            0x00022013 -> 0x00022097
- [x] f216_bit4_update_table_1cc7                0x0002204a -> 0x000220ce
- [x] f216_low_nibble_update_table_1cc3          0x0002207f -> 0x00022103
- [x] f218_shift_in_f216_low_nibble              0x000220e9 -> 0x0002216d
- [x] f224_threshold_tier_and_change_flag        0x0002214a -> 0x000221ce
- [x] stub_zero_0x22193                         0x00022193 -> 0x00022217
- [x] ef9e_latch_from_multi_threshold_check      0x00022197 -> 0x0002221b
- [x] efa0_max_hold_and_recovered_check          0x000221f0 -> 0x00022274
- [x] f226_bit7_update_from_f4c2_check           0x00022225 -> 0x000222a9
- [x] f226_bit8_update_from_f4c0_check           0x00022256 -> 0x000222da
- [x] check_flag_f0f8_bit2_clear                 0x00022377 -> 0x000223fb
- [x] aux_load_condition_check                   0x000223a0 -> 0x00022424
- [x] o2_heater_ready_flag_update                0x00022442 -> 0x0002249b
- [x] closedloop_inhibit_check                   0x000224ba -> 0x00022513
- [x] cranking_detect_check                      0x000224e9 -> 0x00022542
- [x] rpm_sync_ready_check                       0x000226de -> 0x00022737
- [x] o2_ready_timer_update                      0x0002279a -> 0x00022801  (FIXED -- __stdcall_far root cause, resolved)
- [x] f216_bits_f188_f17a_update_and_warmup_gate 0x000228ed -> 0x00022954  (FIXED -- __stdcall_far root cause; storage confirmed correct via get_function_variables despite decompiler display anomaly, see plate comment)
- [x] f20e_bit1_mirror_from_f1fe_bit3            0x000229c0 -> 0x00022a2d
- [x] f21c_bit12_source_condition_check          0x00022c11 -> 0x00022c7e
- [x] f21c_bit1_source_condition_check           0x00022c74 -> 0x00022ce1
- [x] status_word_composite_multibit_update_via_table 0x00022d12 -> 0x00022d7f  (param typed as raw ushort segment-low-word, not a real pointer -- see 24-bit addressing note)
- [x] o2_sensor2_threshold_flag_update_f226_bit13 0x00022f16 -> 0x00022f5f
- [x] f224_bit10_update_from_f20e_check          0x00022f82 -> 0x00022fcb
- [x] init_state_block_ee98_80                   0x00023006 -> 0x00023086
- [x] f2f0_f2f8_ring_and_f27x_f2cc_periodic_init 0x00023027 -> 0x000230a7  (CONFIRMED via disassembly -- genuine void(void), no link FP / no stack params at all, no far-pad needed)
- [x] f07c_multi_channel_threshold_gate_check    0x00023145 -> 0x000231c5
- [x] f216_bit5_hysteresis_gate_check            0x00023193 -> 0x00023213
- [x] f110_f17a_threshold_gate_check             0x00023346 -> 0x000233c6
- [x] f25e_bit14_update_from_f186_f17a_gate      0x00023371 -> 0x000233f1
- [x] f190_f196_select_by_f1f0_f21c_gate         0x00023424 -> 0x000234a4
- [x] efba_timer_target_select_from_f2a0_thresholds 0x00023606 -> 0x00023686
- [x] efbc_timer_target_select_from_f2c6_thresholds 0x00023660 -> 0x000236e0
- [ ] f2b6_knock_retard_state_select              0x0002369a -> 0x0002371a  (SKIPPED -- low confidence per own plate comment, param overwritten before use, condition-flag semantics untraced)
- [x] calc_staged_index_f0f8                     0x00023bf9 -> 0x00023c91  (CONFIRMED via disassembly -- genuine void(void), no stack params, only a local at -0x2:FP)
- [x] f1fe_bit3_clear_and_f1f2_bit4_set_check    0x000242c1 -> 0x0002433c
- [x] f07a_default_reset_return_0x80             0x00024596 -> 0x00024611
- [x] injpw_airvol_reset_on_fuelcut               0x00024680 -> 0x000246fb
- [x] f24e_f254_f970_f972_reset_on_f20e_bit4     0x000246ae -> 0x00024729
- [x] mirror_f18a_to_f18e                        0x00024f76 -> 0x00024ff6
- [x] f0f8_bit12_active_bit11_clear_check        0x00024fb4 -> 0x00025034
- [x] tcu_slip_duty_gain_condition_check          0x00025057 -> 0x000250d7
- [x] f0ec_bit1_threshold_gate_check             0x0002510f -> 0x0002518f
- [x] f3ba_f3bc_f3a4_hysteresis_update            0x0002513a -> 0x000251ba
- [x] f3a4_bit8_hysteresis_update                0x0002519e -> 0x0002521e
- [x] knock_counter_condition_override_eec6      0x00025277 -> 0x000252f7
- [x] f33e_bit2_source_condition_check           0x00025378 -> 0x000253f8
- [x] f33e_bit12_clear                          0x000254d7 -> 0x00025557
- [x] f20e_bit15_source_condition_check          0x0002555e -> 0x000255de
- [x] f33e_bit1_hysteresis_gate_check            0x000255d4 -> 0x00025654
- [x] select_value_f194_f196                     0x000258c4 -> 0x0002592c
- [x] f33e_bit15_hysteresis_update                0x00025cff -> 0x00025d59
- [x] f3fa_f3fe_target_select_by_f0f8_bit5       0x00026271 -> 0x0002628f
- [x] update_max                                 0x000268b3 -> 0x000268f1  (FIXED -- root cause found: far-called function needs __stdcall_far (non-allstack), not __stdcall_far_allstack; extra far-return word shifts stack offset to 0x6. Params: _unused_far_pad, value)
- [x] calc_f40e_threshold_select                 0x000268c4 -> 0x00026902
- [x] f3f0_bit6_clear                           0x0002697c -> 0x000269ba
- [x] f0f8_bit_based_constant_select              0x00026a63 -> 0x00026aa7
- [x] efc8_zero_condition_check                   0x00026aad -> 0x00026af1
- [x] isc_f428_condition_calc                     0x00026b8d -> 0x00026c03
- [x] isc_f3f2_bit6_hysteresis_gate_check         0x00026c2e -> 0x00026ca4
- [x] isc_f084_f3f0_bit8_update                   0x00026ca4 -> 0x00026d1a
- [x] isc_f3f0_bit2_hysteresis_gate_check         0x00026d86 -> 0x00026dfc
- [x] f490_bits01_or_default_select               0x00026dfa -> 0x00026e70
- [x] isc_f3f0_bit3_and_f434_update                0x00026e0e -> 0x00026e84
- [x] isc_efd0_gate_condition_check               0x0002710d -> 0x00027183
- [x] f3f0_bit0_update                           0x000271f8 -> 0x0002726e
- [x] f3f4_bit0_update_and_check                  0x0002721a -> 0x00027290
- [x] f0f8_bit5_constant_select                   0x0002739e -> 0x00027414
- [x] isc_efd4_gate_condition_check               0x00027428 -> 0x0002749e
- [x] f216_bit6_constant_select                   0x00027792 -> 0x000277de
- [x] isc_f42e_or_default_select                  0x000277b8 -> 0x00027804
- [x] isc_f038_constant_select                    0x000277de -> 0x0002782a
- [x] f490_bits01_constant_select                 0x0002785a -> 0x000278a6
- [x] f3f0_bit8_constant_select                   0x000278a4 -> 0x000278f0
- [x] f0f8_masked_constant_select                 0x000278ca -> 0x00027916
- [x] select_const_by_flags_eeca                  0x000279f1 -> 0x00027a43
- [x] isc_f3fa_f3fc_f3fe_select                   0x00027b6e -> 0x00027a43  (collides w/ select_const_by_flags_eeca target)
- [x] mirror_f406_f408_to_f40a_f40c               0x00027c6d -> 0x00027cbf
- [x] warmup_state_f594_f0e6_init                 0x00027c86 -> 0x00027d06
- [x] eeea_bit0_update_on_efa2                    0x00027d33 -> 0x00027db3
- [x] f510_f512_f00e_f514_reset                   0x00028b1b -> 0x00028b0d
- [x] f430_clear                                 0x00028f13 -> 0x00028d13
- [x] f432_clear                                 0x00028f1b -> 0x00028d13  (collides w/ f430_clear target)
- [ ] stub_empty_0x28f80                         0x00028f80 -> 0x0001519e  (part of 15-way stub collision, see below -- not touched)
- [x] o2_wideband_state_cold_init                 0x00028f82 -> 0x00028d82
- [x] o2_wideband_state_warm_init                 0x00028fbc -> 0x00028dbc
- [x] tcu_periodic_timer_update                   0x0002a796 -> 0x0002a54e
- [x] tcu_gear_ratio_state_init                   0x0002a980 -> 0x0002a700
- [x] update_max_f04e                            0x0002bdb3 -> 0x0002b88e  (FIXED -- same __stdcall_far root cause as update_max, resolved)
- [x] tcu_f050_max_update                        0x0002bdc7 -> 0x0002b88e  (collides w/ update_max_f04e target, confirmed genuinely different -- FIXED, same __stdcall_far root cause)

Near-1.0 matches (0.92-0.99) -- excellent candidates, not literally byte-
identical, so verify before blind rename
-----------------------------------------------------------------------
- [x] mirror_status_f0ea_to_ports               0x0001578f -> ?  (0.9925)
- [x] init_state_block_f97a                     0x00015b3f -> ?  (0.96)
- [x] isr_sci1_eri_reset_timeout                 0x00015c0a -> ?  (0.96)
- [x] sci3_timeout_set_retry                     0x00015e79 -> ?  (0.9618)  (FIXED -- same pattern as sci3_timeout_set_abort, __stdcall_far_allstack, storage confirmed via get_function_variables)
- [x] peripheral_block_ff00_warm_init            0x00016fe2 -> ?  (0.9242)
- [x] ign_advance_table_lookup                   0x000173e0 -> ?  (0.9166)  (CONFIRMED via disassembly -- genuine void(void), no link FP, in_ram_113a/c/e reads are fixed ROM table constants not stack params, no fix needed)
- [x] egr_valve_state_eval_f490                  0x00018848 -> ?  (0.9432)  (CONFIRMED via disassembly -- genuine void(void), pbStack_4/EP/offset are internally-initialized locals, not caller params)
- [x] purge_enable_check                        0x00018dca -> ?  (0.9425)  (CONFIRMED via disassembly -- genuine void(void), stack read is an internally-initialized local, no fix needed)
- [x] fueling_throttle_zone_flags_update          0x00021b2d -> ?  (0.985)  (CONFIRMED via disassembly -- genuine void(void), no link FP at all, in_ram_a62/a68 are fixed ROM constants not stack params)
- [x] f224_bits01_update_and_efa8_edge_latch     0x00022c89 -> ?  (0.9813)  (CONFIRMED via disassembly -- genuine void(void), in_ram_8e8/8ea are fixed ROM constants, -0x2:FP is a local snapshot of f224, no caller params)
- [x] status_word_bit3_conditional_update_via_table 0x000232c3 -> ?  (0.9747)  (FIXED -- __stdcall_far root cause, resolved. Param typed as ushort table_offset, not a true 4-byte pointer per the architecture's 24-bit addressing limitation)
- [x] efc2_threshold_update                      0x000252f9 -> ?  (0.9625)  (CONFIRMED via disassembly -- genuine void(void), no link FP, in_ram_b24 is a fixed ROM constant)
- [x] f25a_f2xx_state_mirror_update              0x00024d3a -> ?  (0.985)  (CONFIRMED via disassembly -- genuine void(void), no link FP, in_ram_30a is a fixed ROM constant)
- [x] f516_request_latch_f09a_calib_select        0x00027e1a -> ?  (0.9727)  (CONFIRMED via disassembly -- genuine void(void), no link FP, in_ram reads are fixed ROM constants)
- [x] f502_state_index_update                    0x00027f60 -> ?  (0.981)  (FIXED -- __stdcall_far root cause, resolved. Param: advance_flag)
- [x] knock_octane_pattern_match_state_machine    0x00028557 -> ?  (0.9852)
- [x] f516_hibits_f520_f0f2_mode_select           0x00028700 -> ?  (0.9458)
- [x] f00e_f520_f526_gate_condition_check         0x00028acf -> ?  (0.933)

Known collisions on this ROM (same pattern as w4a51 -- structural, not
ROM-specific; do not rename blindly)
-----------------------------------------------------------------------
- [x] 15 stub_empty_*/noop_return* names (incl. noop_return @ 0x151a0,
      noop_return_void @ 0x15b0b, stub_empty_193f0, stub_empty_0x16158,
      stub_empty_0x1615a, stub_empty_0x1715e, stub_empty_0x17300,
      stub_empty_0x2495a, stub_empty_0x26b8b, stub_empty_0x26e76,
      stub_empty_0x28f80, stub_empty_0x2a8cf, stub_empty_0x2a8d1,
      stub_empty_0x2c129) all fuzzy-match Evo5 0x0001519e. RESOLVED
      2026-07-24: these are all genuinely distinct trivial 1-instruction
      stubs on the 4g63t ROM (different addresses, same shape) -- no
      merge/rename needed since only 4g63t is edited; the shared Evo5
      target just reflects Evo5 having fewer/merged stub instances.
      Each already correctly named individually on 4g63t.
- [x] gear_indexed_table_lookup_f1fc (4g63t 0x000149a7) also matches Evo5
      0x00014880, same target as table_read_indexed (4g63t 0x00014880).
      RESOLVED: confirmed genuinely different functions -- table_read_indexed
      takes explicit (ep_bank, offset) params (typed), gear_indexed_table_lookup_f1fc
      has a non-binding stack passthrough offset (left skipped, same class
      as other stack-passthrough cases in this file).
- [x] latch_request_f588 (0x166cd) / sci_request_latch_f58a_conditional
      (0x1677c) both -> Evo5 0x166e3. RESOLVED: confirmed genuinely different
      (parallel SCI channels, different registers f588/f522/fecb vs
      f58a/f524/fed3). Both typed and correctly named already.
- [x] sci1_rx_frame_accumulator (0x16716) / fedd5_fifo_rx_store_byte
      (0x167c5) both -> Evo5 0x1672c. RESOLVED: confirmed genuinely different
      (SCI1 vs SCI2/3 receive accumulators, different registers). Both typed.
- [x] sci_fifo_f58a_advance_and_load_fed3 (0x16786, score 0.915) also lands
      on Evo5 0x1672c -- three-way collision with the pair above, worse
      than the w4a51 case. RESOLVED: confirmed genuinely different (tx-fifo
      advance/load, not a receive accumulator). Typed as void(void).
- [x] flag_read_ff43_bit0_inverted (0x16a97) -> Evo5 0x15549, same target
      as check_flag_f0d8_bit0_clear (0x15549, score 1.0 on its own address).
      RESOLVED: confirmed genuinely different (different RAM addresses
      ff43 vs f0d8, same bit-check shape). Both typed.
- [x] f430_clear (0x28f13) / f432_clear (0x28f1b) both -> Evo5 0x28d13.
      RESOLVED: confirmed genuinely different addresses/registers, both typed.
- [x] update_max_f04e (0x2bdb3) / tcu_f050_max_update (0x2bdc7) both ->
      Evo5 0x2b88e. Confirmed genuinely different functions. RESOLVED: root
      cause of the param-binding issue found and fixed (far-call offset,
      needs __stdcall_far not __stdcall_far_allstack) -- both now typed.
- [x] select_const_by_flags_eeca (0x279f1) / isc_f3fa_f3fc_f3fe_select
      (0x27b6e) both -> Evo5 0x27a43. RESOLVED: confirmed genuinely different,
      both typed.
- [x] o2_downstream_mode20_select (0x1a228) / o2_sensor2_mode20_select
      (0x1a212) both -> Evo5 0x1a292. RESOLVED (already noted in each
      function's plate comment): confirmed genuinely different (different
      flags checked, different output registers f5b8 vs f5b6). Both still
      skipped for typing due to non-binding stack passthrough, same as
      other O2 mode-select functions in this file -- collision itself is
      resolved, no rename needed on either.

Next steps
-----------------------------------------------------------------------
1. Apply the already-verified 4g63t prototypes/types (done in functions.md)
   to each Evo5 address above -- should be a direct carry-over given the
   1.0 match, not fresh reverse-engineering, EXCEPT where a collision is
   flagged (verify those individually first).
2. Resolve the ~10 collisions listed above before renaming those specific
   addresses -- same caution as the w4a51 collision list.
3. Spot-check a few of the near-1.0 (non-collision) matches by decompiling
   both sides before renaming, since "near" identical could still hide a
   meaningful difference worth flagging.
4. Once settled, this ROM (plus w4a51) gives two independent confirmations
   for the FID database step already planned in functions.md/review.md.
