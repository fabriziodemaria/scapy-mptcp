import logging
logging.getLogger("scapy.runtime").setLevel(logging.DEBUG)

from scapy.all import *
from scapy.layers.inet import TCP, IP, Neighbor
from scapy.layers import mptcp
from scapy.sendrecv import sr1
import random
from scapy.all import sr1
from netaddr import *
import netaddr
from sniff_script import getAck, getPorts

#TODO: add the ability to scan checksum support
#TODO: add the ability to scan HMAC or other auth support
#TODO: add the ability to test MP_Join through networks, maybe via different interfaces?
#TODO: Consider porting over the ability to do tracebox-like failure analysis
#TODO: Add optional host-up checks
#TODO: Change target IPs to plain targets (to allow for dns entries)
#TODO: Make sure all params are consistently ordered and named throughout
#TODO: add address/port randomisation (modulus ringbuffers)


def randintb(n):
    return random.randrange(0, 1L<<(n-1))


def makeMPAddAddr(sourceAddr, sport, dstAddr, dport, initTCPSeq, initTCPAck):

    if initTCPSeq is None: initTCPSeq = randintb(32)
    if initTCPAck is None: initTCPAck = randintb(32)

    pkt = (IP(version=4L,src=sourceAddr,dst=dstAddr)/        \
        TCP(sport=sport,dport=dport,flags="A",seq=initTCPSeq,ack=initTCPAck, \
        options=[TCPOption_MP(mptcp=MPTCP_AddAddr(
                            address_id=5,
                            adv_addr=get_local_ip_address(dstAddr)))]))
    #print pkt.show()
    return pkt


def defaultScan(srcIP, dstIP, sniffAck, srcPort, sniffPort):
    timeout=2

    gatewayIP = Route().route(str(dstIP))[2]
    if gatewayIP == '0.0.0.0':
        print "... on local network...",
        arpadd = getmacbyip(str(dstIP))
        if arpadd == None:
            print " not got MAC, skipping"
            return
        if arpadd == "ff:ff:ff:ff:ff:ff":
            print "This appears to be localhost?"
        else:
            print " at ARP:", arpadd
    else:
        print "Via", gatewayIP, " Not on local network"

    response = []
    pk_list = []
    ack = sniffAck + 2000000
    while ack < sniffAck +  3000000:
        pk_list.append(makeMPAddAddr(srcIP,srcPort,dstIP,sniffPort,1,ack))
        ack += 142700
    response.append(sr1(pk_list,timeout=timeout, verbose=True))
    for element in response:
        if element is None:
            pass
        else:
            element.show()
    return

def parse_args():
    import argparse
    import itertools
    import sys

    parser = argparse.ArgumentParser(description='Network scanner to test hosts for multipath TCP support. Requires root privileges for scapy.')
    parser.add_argument('sourceIP', action='store', help='Source IP address')
    parser.add_argument('destinationIP', action='store', help='Destination IP address')
    parser.add_argument('port', action="store",
                        help='Server port')
    parser.add_argument('interface', action="store",
                            help='Sniffing interface')

    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    return args


def get_local_ip_address(target):
    """Return the the IP address suitable for the target (ip or host)

    This appears to be the best cross platform approach using only
    the standard lib. Better ideas welcome.
    """
    #TODO: handle err if no suitable IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((str(target), 8000))
    ipaddr = s.getsockname()[0]
    s.close()
    return ipaddr


def main():
    args = parse_args()
    portList = getPorts(args.interface)
    dstPort = 0
    if portList[0] == int(args.port):
        dstPort = portList[1]
    else:
        dstPort = portList[0]
    #print dstPort
    defaultScan(args.sourceIP, args.destinationIP, getAck(args.interface, args.port), int(args.port), dstPort)

if __name__ == "__main__":
    main()
# vim: set ts=4 sts=4 sw=4 et:
