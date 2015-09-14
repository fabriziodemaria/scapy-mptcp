import logging
import threading
logging.getLogger("scapy.runtime").setLevel(logging.DEBUG)

from scapy.all import *
from scapy.layers.inet import TCP, IP, Neighbor
from scapy.layers import mptcp
from scapy.sendrecv import sr1
import random
from scapy.all import *
from netaddr import *
import netaddr


class SYNThread (threading.Thread):
    def __init__(self, threadID, name, counter):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter
    def run(self):
        sniff_SYN()


def get_local_ip_address(target):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((str(target), 8000))
    ipaddr = s.getsockname()[0]
    s.close()
    return ipaddr


def makeMPAddAddr(sourceAddr, sport, dstAddr, dport, initTCPSeq, initTCPAck):


    pkt = (IP(version=4L,src=sourceAddr,dst=dstAddr)/        \
        TCP(sport=sport,dport=dport,flags="A",seq=initTCPSeq,ack=initTCPAck, \
        options=[TCPOption_MP(mptcp=MPTCP_AddAddr(
                            address_id=5,
                            adv_addr=get_local_ip_address(dstAddr)))]))
    #print pkt.show()
    return pkt


def defaultScan(srcIP, srcPort, dstIP, dstPort, sniffedSeq, sniffedAck):

    timeout=2

    pk_list = []
    pk_list.append(makeMPAddAddr(srcIP, srcPort, dstIP, dstPort, \
                   sniffedSeq, sniffedAck))
    response = []
    #TODO Handle retransmission in case of no answer
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


def sniff_SYN():
    synlist = sniff(iface='tap0', filter="tcp[13] = 2", timeout=1, count=5)
    #This is bad, should be improved
    synlist[len(synlist)-1].show()


def main():
    thread1 = SYNThread(1, "Syn capturing thread", 1)
    thread1.start()

    args = parse_args()
    p = sniff(iface='tap0', filter="src host 10.1.1.2", timeout=100, count=1)
    defaultScan(args.sourceIP, int(args.port), args.destinationIP, p[0][TCP].sport, (p[0][TCP].ack), (p[0][TCP].seq)+1427)

    thread1.join()

if __name__ == "__main__":
    main()
