# udp_broadcast.py

"""
KK7JXG simple UDP Broadcast of ADIF data
email:barry.shaffer@gmail.com
GPL V3
"""

import socket

def broadcast_adif(adif_data: str, address_port: str) -> str:
    """
    Broadcasts ADIF data over UDP.

    Takes 2 inputs:

    A string containing the ADIF data to broadcast.

    A string defining the broadcast address and port, example: '192.168.1.255:50000'

    Returns a success message if the data is successfully broadcasted,
    otherwise returns an error message.
    """

    try:
        # Split the address and port
        broadcast_address, port = address_port.split(':')

        # Create a UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Enable broadcasting mode
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Send the ADIF data
        sock.sendto(adif_data.encode(), (broadcast_address, int(port)))

        # Close the socket
        sock.close()

        return "UDP broadcast successful"
    except Exception as e:
        return f"Error broadcasting data: {str(e)}"
