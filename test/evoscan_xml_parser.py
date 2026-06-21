# Automatic ECU Table Mapper from EcuFlash XML Definitions
# @category MitsubishiECU

import os
import xml.etree.ElementTree as ET
from ghidra.program.flatapi import FlatProgramAPI
from ghidra.util.task import TaskMonitor

flat_api = FlatProgramAPI(currentProgram)
addr_space = currentProgram.getAddressFactory().getDefaultAddressSpace()

# CONFIGURATION: Set the path to your specific ECU definition XML file
# (This script will automatically follow and read the <include> references if they are in the same folder)
XML_PATH = r"C:\Users\administrator\Downloads\21000011_1997-2001_RVR_X3_Mt__4g63t_.xml"

def parse_and_map_xml(file_path):
    if not os.path.exists(file_path):
        print("XML File not found: {}".format(file_path))
        return

    print("Processing XML definition file: {}".format(file_path))
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except Exception as e:
        print("Failed to parse XML file {}: {}".format(file_path, e))
        return

    # Handle parent includes (like <include>RVR_base</include>)
    base_dir = os.path.dirname(file_path)
    for include_tag in root.findall('include'):
        include_name = include_tag.text.strip()
        if not include_name.endswith('.xml'):
            include_name += '.xml'
        include_path = os.path.join(base_dir, include_name)
        if os.path.exists(include_path):
            parse_and_map_xml(include_path)

    # Find all 2D/3D tables
    tables_found = 0
    for table in root.findall('table'):
        name = table.get('name')
        addr_str = table.get('address')

        if not name or not addr_str:
            continue

        try:
            # Parse hexadecimal XML address
            xml_address = int(addr_str, 16)

            # Convert XML offset convention (+0x10000) to physical 0x000000 address
            ghidra_offset = xml_address - 0x10000

            # Ensure address fits within the physical 128KB ROM bounds (0x0 to 0x1FFFF)
            if 0 <= ghidra_offset <= 0x01FFFF:
                target_addr = addr_space.getAddress(ghidra_offset)

                # Replace illegal characters for Ghidra symbols
                safe_name = name.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")

                # Check if a label already exists to avoid overwriting clean work
                existing_symbol = flat_api.getSymbolAt(target_addr)
                if not existing_symbol:
                    flat_api.createLabel(target_addr, safe_name, True)
                    print("Mapped Table: 0x{:06X} -> {}".format(ghidra_offset, safe_name))
                    tables_found += 1
                else:
                    # Append description text to the existing label instead of forcing a collision
                    flat_api.setPlateComment(target_addr, "EcuFlash Table: {}".format(name))

        except ValueError:
            # Skip tables without static address numbers (like dynamically computed sub-axis references)
            continue

    print("Finished file {}: Created {} new table tags.".format(os.path.basename(file_path), tables_found))

# Run the automation transaction
tx = currentProgram.startTransaction("Auto-Map ECU Tables")
try:
    parse_and_map_xml(XML_PATH)
    print("ECU Table Mapping Sequence Successfully Concluded!")
except Exception as e:
    print("Mapping Transaction Interrupted: {}".format(e))
finally:
    currentProgram.endTransaction(tx, True)
