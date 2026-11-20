package h8539f;

/**
 * Chip-level memory map facts for the H8/539F, shared by the H8 analyzers. Nothing here is
 * specific to any firmware: it is the flash window, the page-0 alias of flash and the start of
 * on-chip RAM/registers.
 */
final class H8MemoryMap {

    /** Flash is one image visible at 0x10000-0x2FFFF. */
    static final long FLASH_START = 0x10000L;
    static final long FLASH_END = 0x2ffffL;

    /** Page 0's 0x0000-0x3FFF is an alias of 0x10000-0x13FFF. */
    static final long MIRROR_END = 0x3fffL;

    /** Page-0 offsets from here up are on-chip RAM/registers, not flash. */
    static final long RAM_START = 0xee80L;

    private H8MemoryMap() {
    }
}