class Canal:
    def __init__(self, nome):
        self.nome = nome
        self.membros = []
    
    def adicionar_membro(self, membro):
        self.membros.append(membro)

    def get_membros(self):
        return self.membros
    
    def remover_membro(self, membro):
        self.membros.remove(membro)
    
    def get_nome(self):
        return self.nome