import inspect
from subprocess import check_output as execCommand
from scapy.all import rdpcap
import tempfile


def sniff_first_syn(i):
    try:
        tf = tempfile.NamedTemporaryFile()
        execCommand("sudo tcpdump -c 1 -w " + tf.name + ".cap -i " + i + " \"tcp[tcpflags] & tcp-syn != 0\" 2>/dev/null", shell = True)
        scan = rdpcap("" + tf.name + ".cap")
    finally:
        execCommand("rm -f " + tf.name + ".cap", shell = True)
    return scan[0]


def sniff_first_synack(i, srcIP):
    try:
        tf = tempfile.NamedTemporaryFile()
        execCommand("sudo tcpdump -c 1 -w " + tf.name + ".cap -i " + i + " \"tcp[tcpflags] & (tcp-syn) != 0 and src net " + srcIP + "\" 2>/dev/null", shell = True)
        scan = rdpcap("" + tf.name + ".cap")
    finally:
        execCommand("rm -f " + tf.name + ".cap", shell = True)
    return scan[0]


def sniff_first_ack(i, dstIP):
    try:
        tf = tempfile.NamedTemporaryFile()
        execCommand("sudo tcpdump -c 1 -w " + tf.name + ".cap -i " + i + " \"tcp[tcpflags] & (tcp-ack) != 0 and tcp[tcpflags] & (tcp-syn) == 0 and dst net " + dstIP + "\" 2>/dev/null", shell = True)
        scan = rdpcap("" + tf.name + ".cap")
    finally:
        execCommand("rm -f " + tf.name + ".cap", shell = True)
    return scan[0]


def sniff_first_start(i, srcIP):
    try:
        tf = tempfile.NamedTemporaryFile()
        execCommand("sudo tcpdump -c 1 -w " + tf.name + ".cap -i " + i + " \"src net " + srcIP + "\" 2>/dev/null", shell = True)
        scan = rdpcap("" + tf.name + ".cap")
    finally:
        execCommand("rm -f " + tf.name + ".cap", shell = True)
    return scan[0]
