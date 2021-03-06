import asyncio
from tcputils import *
import random
from collections import deque 

import struct
import time


class Servidor:
    def __init__(self, rede, porta):
        self.rede = rede
        self.porta = porta
        self.conexoes = {}
        self.callback = None
        self.rede.registrar_recebedor(self._rdt_rcv)

    def registrar_monitor_de_conexoes_aceitas(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que uma nova conexão for aceita
        """
        self.callback = callback

    def _rdt_rcv(self, src_addr, dst_addr, segment):
        src_port, dst_port, seq_no, ack_no, \
            flags, window_size, checksum, urg_ptr = read_header(segment)

        if dst_port != self.porta:
            # Ignora segmentos que não são destinados à porta do nosso servidor
            return
        if not self.rede.ignore_checksum and calc_checksum(segment, src_addr, dst_addr) != 0:
            print('descartando segmento com checksum incorreto')
            return

        payload = segment[4*(flags>>12):]
        id_conexao = (src_addr, src_port, dst_addr, dst_port)

        if (flags & FLAGS_SYN) == FLAGS_SYN:
            # A flag SYN estar setada significa que é um cliente tentando estabelecer uma conexão nova

            conexao = self.conexoes[id_conexao] = Conexao(self, id_conexao, seq_no, ack_no + 1, dst_addr, dst_port, src_addr, src_port)
            # Handshake aceitando a conexão
            ack_no += seq_no + 1    # Próximo pacote esperado
            seq_no_to_send = random.randint(0, 0xffff)  # Define o seq_no desse lado da conexão
            header = make_header(dst_port, src_port, seq_no_to_send, ack_no, FLAGS_SYN|FLAGS_ACK)
            
            header = fix_checksum(header, dst_addr, src_addr)
            # pode enviar um payload futuramente
            conexao.enviar(header, 1)

            if self.callback:
                self.callback(conexao)
        elif id_conexao in self.conexoes:
            # Passa para a conexão adequada se ela já estiver estabelecida

            # Verifica se recebeu o pacote correto
            if seq_no == self.conexoes[id_conexao].seq_no:
                self.conexoes[id_conexao]._rdt_rcv(seq_no, ack_no, flags, payload)

        else:
            print('%s:%d -> %s:%d (pacote associado a conexão desconhecida)' %
                  (src_addr, src_port, dst_addr, dst_port))


class Conexao:
    def __init__(self, servidor, id_conexao, seq_no, ack_no, src_addr, src_port, dst_addr, dst_port):
        self.servidor = servidor
        self.id_conexao = id_conexao
        self.callback = None
        self.seq_no = seq_no + 1   # ACK da outra ponta
        self.ack_no = ack_no       # SEQ da outra ponta
        self.sendbase = seq_no
        self.src_addr = src_addr
        self.src_port = src_port
        self.dst_addr = dst_addr
        self.dst_port = dst_port
        self.closed = False
        self.timer_esta_rodando = False 
        self.fila_de_segmentos = deque([])  # Fila com o segmentos aguardando confirmação de recebimento

        
        #tempo
        
        self.sampleRTT = None
        self.estimatedRTT = None
        self.devRTT = None
        self.primeiro_tempo = True
        self.tempo_inicial = None
        self.tempo_final = None
        self.timeout_interval = 2
        self.timer = None
        
    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        # Recebimento de segmentos provenientes da camada de rede.

        if flags & FLAGS_FIN == FLAGS_FIN:
            # Passando payload vazio para a camada de aplicação indicando que a conexão será fechada
            self.callback(self, b'')
            self.seq_no = self.seq_no + 1
            self.ack_no = ack_no

            # Confirmando o fechamento
            header = make_header(self.src_port, self.dst_port, ack_no, self.seq_no, FLAGS_ACK)
            fix_checksum(header, self.src_addr, self.dst_addr)
            self.servidor.rede.enviar(header, self.dst_addr)
            self.closed = True    # De agora em diante todos os dados recebidos nessa conexão serão ignorados
        elif not self.closed:
            
            print("******************************")
            print("ack_no: %d" %ack_no)
            print("self.ack_no: %d" %self.ack_no)
            print("******************************")
            
            if self.ack_no == ack_no:
                self.tempo_final = time.time()
                print("ack_no recebido: %d" %ack_no)
                self.calcularRTT()
            
            # Verificando o timer
            if seq_no > self.sendbase and (flags & FLAGS_ACK) == FLAGS_ACK:
                
                if len(self.fila_de_segmentos) > 0:
                    self.fila_de_segmentos.popleft()
                    if len(self.fila_de_segmentos) == 0:
                        print("timer cancelado")
                        self.cancelar_timer()
                    else:
                        print("timer receive")
                        self.inicia_timer(self.timeout_interval)

            # Passando dados para a camada de aplicação
            print("desativando tempo")
            self.timer = None
            self.callback(self, payload)

            # proximo a ser recebido
            self.seq_no = self.seq_no + len(payload)
            self.ack_no = ack_no
            # Header que será enviado para confirmar o recebimento
            if len(payload) > 0:
                header = make_header(self.src_port, self.dst_port, ack_no, self.seq_no, FLAGS_ACK)
                fix_checksum(header, self.src_addr, self.dst_addr)
                self.servidor.rede.enviar(header, self.dst_addr)
            # print('recebido payload: %r' % payload)

    # Os métodos abaixo fazem parte da API

    def registrar_recebedor(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que dados forem corretamente recebidos
        """
        self.callback = callback

    def enviar(self, dados, syn = 0):
        resto_payload = b'' # Guarda o resto do payload caso ele seja maior que o tamanho máximo permitido
        """
        Usado pela camada de aplicação para enviar dados
        """
        # envia o segmento para a camada de rede.
        if syn == 0:  # Enviando pacotes normais ('dados' contém somente o payload)
            header = make_header(self.src_port, self.dst_port, self.ack_no, self.seq_no, FLAGS_ACK)
            # Verificando o tamanho do payload
            if len(dados) <= MSS:
                dados = header + dados
            else:       # Payload maior que o tamanho maximo (MSS)
                resto_payload = dados[MSS:]
                dados = header + dados[:MSS]

            dados = fix_checksum(dados, self.src_addr, self.dst_addr)

        self.servidor.rede.enviar(dados, self.dst_addr)
        self.fila_de_segmentos.append(dados) # Colocando na fila para aguardar confirmação
                                             # de recebimento da outra ponta
        self.ack_no += len(dados) - 20  # Próximo pacote esperado pela outra ponta

        if not self.timer_esta_rodando:
            self.tempo_inicial = time.time()
            print("ack_no enviado: %d" %self.ack_no)
            self.inicia_timer(self.timeout_interval)

        if len(resto_payload) != 0:   # Enviando o resto do payload (caso tenha)
            self.enviar(resto_payload)
        pass

    def fechar(self):
        """
        Usado pela camada de aplicação para fechar a conexão
        """
        header = make_header(self.src_port, self.dst_port, self.ack_no, self.seq_no, FLAGS_FIN)
        fix_checksum(header, self.src_addr, self.dst_addr)
        self.servidor.rede.enviar(header, self.dst_addr)
        pass

    def get_seq_no(self):
        return self.seq_no

    def inicia_timer(self, time):
        self.cancelar_timer()
        self.timer = asyncio.get_event_loop().call_later(time, self.timeout)
        

    def cancelar_timer(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None
            self.timer_esta_rodando = False

    def timeout(self):
        # Reenviar o primeiro segmento da fila e reiniciar o timer
        #self.timer_esta_rodando = True
        self.timer = None
        dados = self.fila_de_segmentos.popleft()
        self.fila_de_segmentos.appendleft(dados)  # Recolocando esse segmento no inicio da fila
        self.servidor.rede.enviar(dados, self.dst_addr)
        self.tempo_inicial = time.time()
        self.inicia_timer(self.timeout_interval)
        
    def calcularRTT(self):
        self.sampleRTT = self.tempo_final - self.tempo_inicial
        
        print("sampleRTT: %f" %self.sampleRTT)
        alfa = 0.125
        beta = 0.25
        
        if self.primeiro_tempo:
            self.primeiro_tempo = False
            self.estimatedRTT = self.sampleRTT
            self.devRTT = self.sampleRTT / 2
        else:
            self.estimatedRTT = (1 - alfa) * self.estimatedRTT + alfa * self.sampleRTT
            self.devRTT = (1 - beta) * self.devRTT + beta * abs(self.sampleRTT - self.estimatedRTT)
        self.timeout_interval = self.estimatedRTT + 4*self.devRTT
        print("timeout_Interval: %f" %self.timeout_interval)
