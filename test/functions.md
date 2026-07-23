Cross-Binary Matched Functions -- Prototype/Cleanup Checklist
===============================================================

Generated 2026-07-23 from ghidra:bulk_fuzzy_match (source=4g63t md352553,
target=w4a51 md352554, threshold=0.9). See review.md item 12 for full context.

Purpose: these are functions confirmed shared (byte-identical or near-identical)
across at least two ROM revisions. Cleaning them up here (prototypes, param/
return types, calling convention, struct params where relevant) benefits BOTH
known ROMs immediately and is exactly the kind of signature that should go into
a Function ID (FID) database for recognizing the same functions in an unknown
ROM later.

Columns: [ ] = not yet prototyped/cleaned, [x] = done.
Address pairs are 4g63t (source) -> w4a51 (target). Both now carry the same name.

Math / utility helpers (26) -- all score 1.0, highest confidence group
-----------------------------------------------------------------------
- [ ] sat_add_u16                       0x00014000 -> 0x00014a76
- [ ] sat_sub_u16                       0x00014036 -> 0x00014aac
- [ ] sat_sub_u16_clamp0                0x00014045 -> 0x00014abb
- [ ] sat_mul_u16                       0x0001405c -> 0x00014ad2
- [ ] mul_u16_hi                        0x0001406f -> 0x00014ae5
- [ ] div_u16_sat                       0x000140c0 -> 0x00014b36
- [ ] div_u32_u16_sat                   0x000140dc -> 0x00014b52
- [ ] div_u16_rounded                   0x0001412b -> 0x00014ba1
- [ ] div_s32_s16_rounded               0x00014151 -> 0x00014bc7
- [ ] muldiv_u16                        0x000141ba -> 0x00014c30
- [ ] muldiv_s16_rounded                0x00014219 -> 0x00014c8f
- [ ] mul_u16_x2_sat_alt                0x00014293 -> 0x00014d09
- [ ] mul_u16_x2_sat                    0x000142f3 -> 0x00014d69
- [ ] mul_u16_shr8_sat                  0x0001436c -> 0x00014de2
- [ ] mul_fixedpoint_8                  0x000143bf -> 0x00014e35
- [ ] clamp_u8                          0x0001442d -> 0x00014ea3
- [ ] passthrough_or_sat                0x0001443c -> 0x00014eb2
- [ ] clamp_u16                        0x0001444c -> 0x00014ec2
- [ ] get_high_byte                     0x000144b4 -> 0x00014f2a
- [ ] round_high_byte_signed            0x000144da -> 0x00014f50
- [ ] inc_if_signed_flag                0x000144ef -> 0x00014f65
- [ ] zero_ram_range                    0x0001451a -> 0x00014f90
- [ ] axis_interp_lerp_u8frac_256       0x0001456d -> 0x00014fe3
- [ ] weighted_blend_4term_u8frac       0x000145c5 -> 0x0001503b
- [ ] axis_lookup_interp                0x00014735 -> 0x000151ab
- [ ] axis_interp_lerp_u8frac           0x000147c6 -> 0x0001523c

Named engine functions (17) -- real ECU logic, not generic helpers
-----------------------------------------------------------------------
- [ ] channel_validity_gated_handler_dispatch   0x00014d6f -> 0x000156bf  (score 0.9567)
- [ ] toggle_flag_fe8b_bit4                     0x00015897 -> 0x00015f17
- [ ] trap_hang                                 0x00015b0d -> 0x00015fb4
- [ ] isr_nmi                                   0x000160d9 -> 0x000161a4
- [ ] sci_fifo_f58a_advance_and_load_fed3       0x00016786 -> 0x00016b22  (score 0.915)
- [ ] isr_tpu5_tgi5b_sci1_tie_clear             0x00016865 -> 0x00016928
- [ ] ff0d_clear_bits5_6                        0x00017154 -> 0x00016e36
- [ ] adc_sensor_convert_multi                  0x00017160 -> 0x00016e40
- [ ] byte_sum_banked                           0x00017206 -> 0x00016ee6
- [ ] sum_byte_array                            0x0001722b -> 0x00016f0b
- [ ] memcpy_banked                             0x00017256 -> 0x00016f36
- [ ] boot_ram_block_copy                       0x00020024 -> 0x00014024
- [ ] control_state_latch_prev                  0x00021f70 -> 0x0001e09e
- [ ] rpm_sync_ready_check                      0x000226de -> 0x0001d5f4  (score 0.915)
- [ ] mirror_f18a_to_f18e                       0x00024f76 -> 0x00022e20
- [ ] mirror_f406_f408_to_f40a_f40c             0x00027c6d -> 0x00020273
- [ ] f510_f512_f00e_f514_reset                 0x00028b1b -> 0x00020e16

Flagged collisions -- resolve BEFORE prototyping, not part of the 43 above
-----------------------------------------------------------------------
- [ ] w4a51 0x00015fb2 -- 15 different 4g63t stub_empty_*/noop_return* names
      all fuzzy-match this one target (expected: they're trivially identical
      empty/one-instruction stubs in the source ROM too). Decide on ONE name
      (suggest generic \"noop_return\") rather than picking arbitrarily.
- [ ] w4a51 0x00016b18 -- latch_request_f588 (4g63t 0x000166cd) AND
      sci_request_latch_f58a_conditional (4g63t 0x0001677c) both match.
      Needs decompile-and-compare: same function on w4a51, or has 4g63t's
      split been merged?
- [ ] w4a51 0x00016b61 -- sci1_rx_frame_accumulator (4g63t 0x00016716) AND
      fedd5_fifo_rx_store_byte (4g63t 0x000167c5) both match. Same situation
      as above.
- [ ] DISCARD -- update_max (4g63t 0x000268b3, score 0.9) matched to w4a51
      0x00014aac, which already holds sat_sub_u16 at score 1.0. Almost
      certainly a false positive (similar instruction shape, different
      function). Do not rename; leave w4a51 0x14aac as sat_sub_u16 only.

Next steps (see review.md item 12 for full detail)
-----------------------------------------------------------------------
1. Work through the checklist above: set real parameter/return types and
   calling convention on each function in BOTH programs (source values are
   best understood in 4g63t; apply the same signature to w4a51).
2. Resolve the four flagged collisions first, since they may add 1-3 more
   entries to the checklist once settled.
3. Once this list is fully checked off, build a Ghidra FID database from the
   4g63t program's cleaned-up function set, and validate it reproduces these
   matches automatically on w4a51 without a manual bulk_fuzzy_match pass.
4. Identify struct candidates among these and the data tables already found
   this session (EECA/EECC/EECE mode-shadow triplet, F5C0-C8 snapshot
   cluster, 0x20a14 range-classification table) for the same treatment.
