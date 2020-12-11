import asyncio
from tcputils import *
import random


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
            ack_no += seq_no + 1
            seq_no_to_send = random.randint(0, 0xffff)  # Define o seq_no desse lado da conexão
            header = make_header(dst_port, src_port, seq_no_to_send, ack_no, FLAGS_SYN|FLAGS_ACK)
            header = fix_checksum(header, dst_addr, src_addr)
            # pode enviar um payload futuramente
            conexao.enviar(header, src_addr)

            if self.callback:
                self.callback(conexao)
        elif id_conexao in self.conexoes:
            # Passa para a conexão adequada se ela já estiver estabelecida
            self.conexoes[id_conexao]._rdt_rcv(seq_no, ack_no, flags, payload)
        else:
            print('%s:%d -> %s:%d (pacote associado a conexão desconhecida)' %
                  (src_addr, src_port, dst_addr, dst_port))


class Conexao:
    def __init__(self, servidor, id_conexao, seq_no, ack_no, src_addr, src_port, dst_addr, dst_port):
        self.servidor = servidor
        self.id_conexao = id_conexao
        self.callback = None
        self.start_of_seq_no = seq_no
        self.seq_no = seq_no
        print(str(seq_no) + 'created\n')
        self.ack_no = ack_no
        self.src_addr = src_addr
        self.src_port = src_port
        self.dst_addr = dst_addr
        self.dst_port = dst_port

        self.timer = asyncio.get_event_loop().call_later(1, self._exemplo_timer)  # um timer pode ser criado assim; esta linha é só um exemplo e pode ser removida
        #self.timer.cancel()   # é possível cancelar o timer chamando esse método; esta linha é só um exemplo e pode ser removida

    def _exemplo_timer(self):
        # Esta função é só um exemplo e pode ser removida
        print('Este é um exemplo de como fazer um timer')

    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        # TODO: trate aqui o recebimento de segmentos provenientes da camada de rede.
        # Chame self.callback(self, dados) para passar dados para a camada de aplicação após
        self.callback(self, payload)
        # garantir que eles não sejam duplicados e que tenham sido recebidos em ordem.
        tam_payload = len(payload)
        print(str(tam_payload) + 'tam_payload\n')
        print(seq_no - self.seq_no - 1)

        # Verificando se esse pacote é o correto
        if tam_payload == (seq_no - self.seq_no - 1):
            self.seq_no = seq_no
            # Header que será enviado para confirmar o recebimento
            # seq_no = ack_no + 1 (próximo pacote que o outro lado da conexao espera receber)
            # ack_no = seq_no (Próximo pacote que esse lado da conexão espera receber)
            make_header(self.src_port, self.dst_port, ack_no, seq_no, FLAGS_ACK)
            self.servidor.rede.enviar('', self.dst_addr)

        print('recebido payload: %r' % payload)

    # Os métodos abaixo fazem parte da API

    def registrar_recebedor(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que dados forem corretamente recebidos
        """
        self.callback = callback

    def enviar(self, dados, dest_addr):
        """
        Usado pela camada de aplicação para enviar dados
        """
        # TODO: implemente aqui o envio de dados.
        # Chame self.servidor.rede.enviar(segmento, dest_addr) para enviar o segmento
        self.servidor.rede.enviar(dados, dest_addr)
        # que você construir para a camada de rede.
        pass

    def fechar(self):
        """
        Usado pela camada de aplicação para fechar a conexão
        """
        # TODO: implemente aqui o fechamento de conexão
        pass

    def get_seq_no(self):
        return self.seq_no