#!/usr/bin/env python2

# cli.py
#
# This file is meant to be executed by the user in order to start
# an interactive CLI. It creates an instance of the framework and
# enters a command loop which is implemented with the readline
# interface. Commands entered by the user are matched to the
# corresponding Cmd subclass in the cmds.py file and dispatched
# accordingly.
#
# Copyright (c) 2018 Dennis Mantz. (MIT License)
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


from __future__ import print_function

import socket
import sys
from builtins import str
import internalblue.utils.pwnlib_wrapper as pwnlib
import os
import traceback
import argparse

from .adbcore import ADBCore
from .hcicore import HCICore
from sys import platform

from . import cmds

try:
    import typing
    from typing import List, Optional
    from internalblue.core import InternalBlue
    from . import DeviceTuple

except:
    pass

HISTFILE = "_internalblue.hist"


def print_banner():
    banner = """\
   ____     __                    _____  __
  /  _/__  / /____ _______  ___ _/ / _ )/ /_ _____
 _/ // _ \/ __/ -_) __/ _ \/ _ `/ / _  / / // / -_)
/___/_//_/\__/\__/_/ /_//_/\_,_/_/____/_/\_,_/\__/


type <help> for usage information!\n\n"""
    for line in banner:
        pwnlib.term.output(pwnlib.text.blue(line))


def commandLoop(internalblue, init_commands=None):
    cmdstack = init_commands.split(";")[::-1] if init_commands else None
    while internalblue.running and not internalblue.exit_requested:
        cmd_instance = None
        try:
            if cmdstack:
                cmdline = cmdstack.pop().strip()
            else:
                cmdline = (
                    pwnlib.term.readline.readline(prompt="> ").strip().decode("utf-8")
                )
            cmdword = cmdline.split(" ")[0].split("=")[0]
            if cmdword == "":
                continue
            pwnlib.log.debug("Command Line: [[" + cmdword + "]] " + cmdline)
            matching_cmd = cmds.findCmd(cmdword)
            if matching_cmd == None:
                pwnlib.log.warn("Command unknown: " + cmdline)
                continue
            cmd_instance = matching_cmd(cmdline, internalblue)
            if not cmd_instance.work():
                pwnlib.log.warn("Command failed: " + str(cmd_instance))
        except ValueError as e:
            pwnlib.log.warn("commandLoop: ValueError: " + str(e))
            raise
        except KeyboardInterrupt:
            if cmd_instance != None:
                cmd_instance.abort_cmd()
            else:
                pwnlib.log.info("Got Ctrl-C; exiting...")
                internalblue.exit_requested = True
                break
        except AssertionError as e:
            raise
        except socket.error as e:
            if e.args == (1, "Operation not permitted"):
                pwnlib.log.critical(
                    "Received an 'Operation not permitted' socket.error, you might need root for the command '{}'".format(
                        cmdline
                    )
                )
                pwnlib.log.critical(traceback.format_exc())
        except Exception as e:
            internalblue.exit_requested = True  # Make sure all threads terminate
            pwnlib.log.critical("Uncaught exception (%s). Abort." % str(e))
            print(traceback.format_exc())
            raise
        cmd_instance = None


def _parse_argv(argv):

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-directory", "-d", help="Set data directory. Default: ~/.internalblue"
    )
    parser.add_argument(
        "--verbose", "-v", help="Set log level to DEBUG", action="store_true"
    )
    parser.add_argument(
        "--ios-device",
        "-i",
        help="Tell internalblue to connect to a remote iPhone HCI socket. Specify socket IP address and port (i.e., 172.20.10.1:1234).",
    )
    parser.add_argument(
        "--serialsu",
        "-s",
        help="On ADB, directly try su/serial/busybox scripting, if you do not have a special bluetooth.default.so file.",
        action="store_true",
    )
    parser.add_argument("--trace", help="Trace hci connection")
    parser.add_argument("--device", help="Specify device/core to be used")
    parser.add_argument(
        "--commands",
        "-c",
        help="CLI command to run before prompting, seperated by ';' (used for easier testing)",
    )
    parser.add_argument(
        "--replay",
        help="Intercept and replace every communication with the core with the one in the specified file",
    )
    parser.add_argument(
        "--save", help="Store a trace into the file that can be used with --replay"
    )
    return parser.parse_args(argv)


# Main Program Start
def internalblue_cli(argv, args=None):
    # print_banner()

    args = args or _parse_argv(argv)

    if args.data_directory is not None:
        data_directory = args.data_directory
    else:
        data_directory = os.path.expanduser("~") + "/.internalblue"
    if not os.path.exists(data_directory):
        os.mkdir(data_directory)

    if args.verbose:
        log_level = "debug"
    else:
        log_level = "info"

    # Readline Completions
    cmd_keywords = []
    for cmd in cmds.getCmdList():
        for keyword in cmd.keywords:
            cmd_keywords.append(keyword)
    readline_completer = pwnlib.term.completer.LongestPrefixCompleter(
        words=cmd_keywords
    )
    pwnlib.term.readline.set_completer(readline_completer)

    if args.trace:
        from .socket_hooks import hook
        from internalblue import socket_hooks

        HookClass = getattr(socket_hooks, args.trace)
        hook(HCICore, HookClass)
        hook(ADBCore, HookClass)
    elif args.save:
        from .socket_hooks import hook, TraceToFileHook

        hook(HCICore, TraceToFileHook, filename=args.save)
        hook(ADBCore, TraceToFileHook, filename=args.save)

    # Initalize cores and get devices
    # As macOS has additional dependencies (objc), only import it here if needed
    connection_methods = []  # type: List[InternalBlue]
    if args.replay:
        from .socket_hooks import hook, ReplaySocket
        from .macoscore import macOSCore

        replay_devices = ["macos_replay", "adb_replay", "hci_replay", "ios_replay"]
        if args.device == "macos_replay":
            from .macoscore import macOSCore

            hook(macOSCore, ReplaySocket, filename=args.replay)
            connection_methods = [
                macOSCore(
                    log_level=log_level, data_directory=data_directory, replay=True
                )
            ]
        elif args.device == "hci_replay":
            hook(HCICore, ReplaySocket, filename=args.replay)
            connection_methods = [
                HCICore(log_level=log_level, data_directory=data_directory, replay=True)
            ]
        elif args.device == "adb_replay":
            hook(ADBCore, ReplaySocket, filename=args.replay)
            connection_methods = [
                ADBCore(log_level=log_level, data_directory=data_directory, replay=True)
            ]
        elif args.device == "ios_replay":
            raise NotImplementedError("ios replay is not implemented yet")
        else:
            raise ValueError(
                "--device is required with --replay and has to be one of {}".format(
                    replay_devices
                )
            )

    elif args.ios_device:
        from .ioscore import iOSCore

        connection_methods = [
            iOSCore(args.ios_device, log_level=log_level, data_directory=data_directory)
        ]
    elif platform == "darwin":
        from .macoscore import macOSCore

        connection_methods = [
            macOSCore(
                log_level=log_level,
                data_directory=data_directory,
                replay=(args.replay and args.device == "mac"),
            ),
            ADBCore(log_level=log_level, data_directory=data_directory),
        ]
        if args.trace:
            hook(macOSCore, HookClass)
        elif args.save:
            hook(macOSCore, TraceToFileHook, filename=args.save)
    else:
        connection_methods = [
            ADBCore(
                log_level=log_level, data_directory=data_directory, serial=args.serialsu
            ),
            HCICore(log_level=log_level, data_directory=data_directory),
        ]

    devices = []  # type: List[DeviceTuple]
    for connection_method in connection_methods:
        devices.extend(connection_method.device_list())

    device = None  # type: Optional[DeviceTuple]
    if len(devices) > 0:
        if args.replay:
            # There should only be one device that was created when --replay was passed
            device = devices[0]
        elif args.device:
            matching_devices = [dev for dev in devices if dev[1] == args.device]
            if len(matching_devices) > 1:
                pwnlib.log.critical("Found multiple matching devices")
                exit(-1)
            elif len(matching_devices) == 1:
                pwnlib.log.info("Found device is: {}".format(matching_devices[0]))
                device = matching_devices[0]
            else:
                pwnlib.log.critical("No matching devices found")
                exit(-1)
        elif len(devices) == 1:
            device = devices[0]
        else:
            i = pwnlib.options("Please specify device:", [d[2] for d in devices], 0)
            device = devices[i]

        # Setup device
        reference = device[0]
        reference.interface = device[1]

        # Restore readline history:
        if os.path.exists(reference.data_directory + "/" + HISTFILE):
            readline_history = pwnlib.read(reference.data_directory + "/" + HISTFILE)
            pwnlib.term.readline.history = readline_history.split(b"\n")

        # Connect to device
        if not reference.connect():
            pwnlib.log.critical("No connection to target device.")
            exit(-1)

        # Enter command loop (runs until user quits)
        pwnlib.log.info("Starting commandLoop for reference {}".format(reference))
        commandLoop(reference, init_commands=args.commands)

        # shutdown connection
        reference.shutdown()

        # Save readline history:
        # TODO: - This causes issues, have to fix ASAP
        # f = open(reference.data_directory + "/" + HISTFILE, "w")
        # f.write("\n".join(term.readline.history))
        # f.close()

    # Cleanup
    pwnlib.log.info("Goodbye")


if __name__ == "__main__":
    internalblue_cli(sys.argv[1:])
