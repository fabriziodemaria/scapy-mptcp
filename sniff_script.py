import os

lista = open('y', 'r').read().split(' ')

for i in range(0,len(lista)-1):
    if lista[i] == "ack":
        print lista[i+1][:-1]