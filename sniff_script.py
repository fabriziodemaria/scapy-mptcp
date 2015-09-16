import inspect
from subprocess import check_output as execCommand
from scapy.all import rdpcap

def sniff_first_syn(i):
    try:
        execCommand("sudo tcpdump -c 1 -w " + inspect.stack()[1][3] + ".cap -i " + i + " \"tcp[tcpflags] & tcp-syn != 0\" 2>/dev/null", shell = True)
        scan = rdpcap("" + inspect.stack()[1][3] + ".cap")
        # execCommand("rm " + inspect.stack()[1][3] + ".cap", shell = True)
    finally:
        execCommand("rm -f " + inspect.stack()[1][3] + ".cap", shell = True)
    return scan[0]

def sniff_first_synack(i):
    try:
        execCommand("sudo tcpdump -c 1 -w " + inspect.stack()[1][3] + ".cap -i " + i + " \"tcp[tcpflags] & (tcp-syn&tcp-ack) != 0\" 2>/dev/null", shell = True)
        scan = rdpcap("" + inspect.stack()[1][3] + ".cap")
        # execCommand("rm " + inspect.stack()[1][3] + ".cap", shell = True)
    finally:
        execCommand("rm -f " + inspect.stack()[1][3] + ".cap", shell = True)
    return scan[0]
