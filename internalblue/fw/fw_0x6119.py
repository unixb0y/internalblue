#!/usr/bin/env python2

# fw_0x6119.py
#
# All firmware specific data such as address offsets are collected
# in the fw.py file. Later versions of the framework will provide
# multiple copies of this file in order to target different firmware
# and chip versions.
#
# Copyright (c) 2019 Jiska Classen. (MIT License)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
# - The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
# - The Software is provided "as is", without warranty of any kind, express or
#   implied, including but not limited to the warranties of merchantability,
#   fitness for a particular purpose and noninfringement. In no event shall the
#   authors or copyright holders be liable for any claim, damages or other
#   liability, whether in an action of contract, tort or otherwise, arising from,
#   out of or in connection with the Software or the use or other dealings in the
#   Software.

# Firmware Infos
# This runs on Rasperry Pi 3+
FW_NAME = "BCM4345C0"

# Memory Sections
class MemorySection:
    def __init__(self, start_addr, end_addr, is_rom, is_ram):
        self.start_addr = start_addr
        self.end_addr = end_addr
        self.is_rom = is_rom
        self.is_ram = is_ram

    def size(self):
        return self.end_addr - self.start_addr

# Memory Sections
#                          start,    end,      is_rom? is_ram?
SECTIONS = [ MemorySection(0x0,      0x90000,  True , False),
             MemorySection(0xd0000,  0xd8000,  False, True ),
            #MemorySection(0xe0000,  0x1f0000, True , False),
             MemorySection(0x200000, 0x228000, False, True ),
             MemorySection(0x260000, 0x268000, True , False),
            #MemorySection(0x280000, 0x2a0000, True , False),
             MemorySection(0x318000, 0x320000, False, False),
             MemorySection(0x324000, 0x360000, False, False),
             MemorySection(0x362000, 0x362100, False, False),
             MemorySection(0x363000, 0x363100, False, False),
             MemorySection(0x600000, 0x600800, False, False),
             MemorySection(0x640000, 0x640800, False, False),
             MemorySection(0x650000, 0x650800, False, False),
            #MemorySection(0x680000, 0x800000, False, False)
            ]

# Connection Structure and Table
CONNECTION_ARRAY_ADDRESS = 0x204ba8
CONNECTION_MAX           = 11
CONNECTION_STRUCT_LENGTH = 0x150