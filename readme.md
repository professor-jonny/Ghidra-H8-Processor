# Hitachi H8/500 Processor for Ghidra

This is a processor definition for the Hitachi H8/500 family of microprocessors for Ghidra.
originally It was based on work by https://github.com/Hurricos
and extended to the H8/520 in maximum mode by https://github.com/c4ashley

https://github.com/professor-jonny expanded to support the h8/539f, this is still a work in progress but the instruction set has been expanded with the three missing instructions from c4ashley'ss branch.

on onboarding and setup example scripts for my h8/539f RVR ECU.
and some helpfull info is included

## Compile & Install
Make sure you have Ghidra installed, with `sleigh` available in the `support` directory.
Change the `GHIDRADIR` variable inside the Makefile to the location where Ghidra is installed.
Run `make && make install`
