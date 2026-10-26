"""Duas arquiteturas pequenas com encoder e saída separáveis na transferência."""

import torch
from torch import nn


class MLP(nn.Module):
    def __init__(self, lookback, n_features, unidades=(32, 16)):
        super().__init__()
        camadas = []
        tamanho = lookback * n_features
        for largura in unidades:
            camadas.extend([nn.Linear(tamanho, largura), nn.ReLU()])
            tamanho = largura
        self.encoder = nn.Sequential(*camadas)
        self.head = nn.Linear(tamanho, 1)

    def forward(self, x):
        return self.head(self.encoder(x.flatten(start_dim=1))).squeeze(-1)


class LSTM(nn.Module):
    def __init__(self, n_features, unidades=16):
        super().__init__()
        self.encoder = nn.LSTM(input_size=n_features, hidden_size=unidades, num_layers=1, batch_first=True)
        self.head = nn.Linear(unidades, 1)

    def forward(self, x):
        # Não recebe nem armazena h/c: começa com zeros para cada janela.
        sequencia, _ = self.encoder(x)
        return self.head(sequencia[:, -1, :]).squeeze(-1)


class MLPResidual(MLP):
    """Prediz y padronizado somando uma correção à potência do último dia.

    A correção usa a escala de y, sem centralizar as diferenças. Assim uma
    correção nula reproduz exatamente a persistência na unidade original.
    """
    def __init__(self, contrato, unidades=(32, 16)):
        super().__init__(contrato["lookback"], len(contrato["variaveis_por_passo"]), unidades)
        self.indice_potencia = contrato["variaveis_por_passo"].index("Active_Power")
        for nome, valor in {
            "media_x_potencia": contrato["x_media_treino"][self.indice_potencia],
            "escala_x_potencia": contrato["x_escala_treino"][self.indice_potencia],
            "media_y": contrato["y_media_treino"],
            "escala_y": contrato["y_escala_treino"],
        }.items():
            self.register_buffer(nome, torch.tensor(float(valor), dtype=torch.float32))

    def forward(self, x):
        potencia_anterior = x[:, -1, self.indice_potencia] * self.escala_x_potencia + self.media_x_potencia
        base_padronizada = (potencia_anterior - self.media_y) / self.escala_y
        return base_padronizada + super().forward(x)


def criar_modelo(tipo, contrato, config):
    if tipo == "mlp":
        return MLP(contrato["lookback"], len(contrato["variaveis_por_passo"]), config["mlp_unidades"])
    if tipo == "lstm":
        return LSTM(len(contrato["variaveis_por_passo"]), config["lstm_unidades"])
    raise ValueError("Modelo deve ser mlp ou lstm.")


def congelar_encoder(modelo):
    """Disponível para a próxima etapa; o pré-treinamento aprende todos os pesos."""
    for parametro in modelo.encoder.parameters():
        parametro.requires_grad = False
    for parametro in modelo.head.parameters():
        parametro.requires_grad = True
    return modelo
