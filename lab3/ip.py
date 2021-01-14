from iputils import *
from ipaddress import ip_network, ip_address
from tcputils import *
from random import randint

class IP:
    def __init__(self, enlace):
        """
        Inicia a camada de rede. Recebe como argumento uma implementação
        de camada de enlace capaz de localizar os next_hop (por exemplo,
        Ethernet com ARP).
        """
        self.callback = None
        self.enlace = enlace
        self.enlace.registrar_recebedor(self.__raw_recv)
        self.ignore_checksum = self.enlace.ignore_checksum
        self.meu_endereco = None

    def __raw_recv(self, datagrama):
        dscp, ecn, identification, flags, frag_offset, ttl, proto, \
           src_addr, dst_addr, payload = read_ipv4_header(datagrama)
        if dst_addr == self.meu_endereco:
            # atua como host
            if proto == IPPROTO_TCP and self.callback:
                self.callback(src_addr, dst_addr, payload)
        else:
            # atua como roteador
            next_hop = self._next_hop(dst_addr)
            # TODO: Trate corretamente o campo TTL do datagrama
            self.enlace.enviar(datagrama, next_hop)

    def _next_hop(self, dest_addr):
        # TODO: Use a tabela de encaminhamento para determinar o próximo salto
        # (next_hop) a partir do endereço de destino do datagrama (dest_addr).
        # Retorne o next_hop para o dest_addr fornecido.
        dest_addr = ip_address(dest_addr)

        for addr in self.tabela:
            ipv4network = addr[0]
            if dest_addr in ipv4network: 
                return str(addr[1])
         
        pass

    def definir_endereco_host(self, meu_endereco):
        """
        Define qual o endereço IPv4 (string no formato x.y.z.w) deste host.
        Se recebermos datagramas destinados a outros endereços em vez desse,
        atuaremos como roteador em vez de atuar como host.
        """
        self.meu_endereco = meu_endereco

    def definir_tabela_encaminhamento(self, tabela):
        """
        Define a tabela de encaminhamento no formato
        [(cidr0, next_hop0), (cidr1, next_hop1), ...]

        Onde os CIDR são fornecidos no formato 'x.y.z.w/n', e os
        next_hop são fornecidos no formato 'x.y.z.w'.
        """
        self.tabela = []
        for addr in tabela:
            self.tabela.append((ip_network(addr[0]), ip_address(addr[1])))
        
        # Ordenando por tamanho do prefixo da rede
        self.tabela.sort(key=lambda addr: addr[0].prefixlen)
        self.tabela.reverse()
        print(self.tabela)
        pass

    def registrar_recebedor(self, callback):
        """
        Registra uma função para ser chamada quando dados vierem da camada de rede
        """
        self.callback = callback

    def enviar(self, segmento, dest_addr):
        """
        Envia segmento para dest_addr, onde dest_addr é um endereço IPv4
        (string no formato x.y.z.w).
        """
        next_hop = self._next_hop(dest_addr)
        # TODO: Assumindo que a camada superior é o protocolo TCP, monte o
        # datagrama com o cabeçalho IP, contendo como payload o segmento.
        vihl = 69
        identification = 0
        ttl = 64
        proto = 6
        
        datagrama = struct.pack('!BBHHHBBH', vihl, 0, 20 + len(segmento), identification, 0, ttl, proto, 0)+ str2addr(self.meu_endereco) + str2addr(dest_addr)
        checksum = calc_checksum(datagrama)

        datagrama = struct.pack('!BBHHHBBH', vihl, 0, 20 + len(segmento), 
            identification, 0, ttl, proto, checksum) + str2addr(self.meu_endereco) + str2addr(dest_addr) + segmento

        self.enlace.enviar(datagrama, next_hop)
