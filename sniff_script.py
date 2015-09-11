import os
import re
from subprocess import call, check_output

def getAck(interface,serverPort):
    output = check_output("sudo tcpdump -i " + interface + " -vS -c 50", shell = True)
    lista = output.split('\n')
    line = ""
    for l in lista:
        if  l.split(" ")[4].split('.')[-1:][0].split(':')[0] == serverPort:
            line = l
            break
    if line == "":
        return
    #print line
    lista = line.split(" ")
    for i in range(0,len(lista)-1):
        if lista[i] == "ack":
            print lista
            return int(re.search(r'\d+', lista[i+1][:-1]).group())

def getPorts(interface):
    ports = []
    output = check_output("sudo tcpdump -i " + interface + " -vS -c 50", shell = True)
    lista = output.split(' ')
    for i in range(0,len(lista)-1):
        if lista[i] == "Flags":
            ports.append(int(lista[i-1].split('.')[-1:][0].split(':')[0]))
            ports.append(int(lista[i-3].split('.')[-1:][0].split(':')[0]))
            return ports
