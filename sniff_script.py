import os
from subprocess import call, check_output

def getAck(interface):
    output = check_output("sudo tcpdump -i " + interface + " -vS -c 50", shell = True)
    lista = output.split(' ')
    for i in range(0,len(lista)-1):
        if lista[i] == "ack":
            return int(lista[i+1][:-1])

def getPorts(interface):
    ports = []
    output = check_output("sudo tcpdump -i " + interface + " -vS -c 50", shell = True)
    lista = output.split(' ')
    for i in range(0,len(lista)-1):
        if lista[i] == "Flags":
            ports.append(int(lista[i-1].split('.')[-1:][0].split(':')[0]))
            ports.append(int(lista[i-3].split('.')[-1:][0].split(':')[0]))
            return ports
