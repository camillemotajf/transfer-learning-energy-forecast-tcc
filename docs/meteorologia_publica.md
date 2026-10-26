> Organização atual: os arquivos de comparação histórica ficam em `data/interim/exploratorio/` e `reports/exploratorio/meteorologia/`; os gráficos estão em `reports/figures/`. A meteorologia atual fica em `data/interim/meteorologia/`.

# Meteorologia pública para a usina Leopoldo

## Fonte e localização

Foi baixada a série **horária Copernicus ERA5 via Open-Meteo** para latitude
**-16,55°**, longitude **-48,85°**, com altitude **927 m** informada à API.
O modelo foi selecionado explicitamente (`models=era5`), sem a combinação automática
de modelos da opção Best Match. [Documentação oficial da consulta](https://open-meteo.com/en/docs/historical-weather-api).

O ERA5 tem resolução aproximada de 0,25°. A resposta identifica uma célula centrada
em **-16,50° / -48,75°**, próxima à usina, e altitude de processamento de 927 m.
São dados de reanálise em grade, não uma estação meteorológica instalada na usina.
A metodologia do ERA5 está descrita por [Hersbach et al. (2020)](https://doi.org/10.1002/qj.3803).

A consulta inclui 02/01/2025–01/01/2026 para completar as bordas horárias.
O conjunto final contém **363 dias: 03/01/2025–31/12/2025**, correspondente ao
calendário da base diária atual da usina. As datas usam `America/Sao_Paulo`.

## Dados e correspondências

| Coluna de referência | Variável pública ou cálculo |
|---|---|
| `Weather_Temperature_Celsius` | Média de 24 valores horários de `temperature_2m`, em °C |
| `Weather_Relative_Humidity` | Média de `relative_humidity_2m`, em % |
| `Wind_Speed` | Média de `wind_speed_10m`, solicitado em m/s |
| `Wind_Direction` | Média circular de `wind_direction_10m`, em graus |
| `Global_Horizontal_Radiation` | Média de `shortwave_radiation`, em W/m² |
| `Diffuse_Horizontal_Radiation` | Média de `diffuse_radiation`, em W/m² |
| `Weather_Daily_Rainfall` | Média do contador acumulado de chuva no dia, reconstruído a partir de `rain` |
| `Radiation_Global_Tilted` | Irradiância global no plano dos módulos, modelo Perez com ERA5 |
| `Radiation_Diffuse_Tilted` | Difusa do céu + refletida pelo solo no plano dos módulos, pelo mesmo cálculo |

As médias são de dias completos, incluindo a noite. Valores de radiação não são
confundidos com energia diária. `GHI_Energy_kWh_m2` e `Rainfall_Total_mm` são
exportados separadamente na tabela meteorológica pública.

As irradiâncias e a chuva da API representam a hora **anterior** ao timestamp.
O código ajusta o rótulo ao início do intervalo antes de agrupar por dia.
Para manter a definição usada nos notebooks da Austrália e do Brasil, a chuva
na coluna de referência é a média do acumulado diário, e não a soma diária.
Assume-se distribuição uniforme da chuva dentro de cada hora, amostrando o
contador de 5 em 5 minutos. Esta aproximação não recupera os horários reais dos
eventos. Direção do vento usa média circular para não tratar 359°/1° como 180°.

## Geometria dos módulos

O arquivo de características fornecido foi consultado sem alteração. Na aba
**Fixa**, B3 contém azimute de 20°, B9 contém um campo rotulado **Ângulo limite**
de 20° e E7 informa albedo de 0,3. A convenção do azimute não está documentada.

Após orientação do usuário, foi adotada **inclinação de 20°** e orientação
**norte (azimute 0° contado no sentido horário desde o norte)** como hipótese.
Esta escolha não é apresentada como azimute confirmado por levantamento de campo.
São calculados também os cenários de 20° e 340°, para verificar a influência da
interpretação da orientação descrita na planilha.

O modelo [Perez do pvlib](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.irradiance.get_total_irradiance.html)
usa GHI, DHI e DNI horários, posição solar no meio da hora e albedo 0,3.
Não são modelados ganho bifacial, perdas elétricas, sombreamento do horizonte
ou de estruturas. Portanto, as colunas inclinadas são estimativas de irradiância
frontal, não previsões da geração elétrica.

Os parâmetros e suas fontes/células estão em `config/usina_leopoldo.json`.
Para mudar a hipótese de orientação, editar `azimute_norte_horario_graus` nesse
arquivo e executar novamente a seção de meteorologia pública no notebook.

## Preenchimento e comparação

O preenchimento utiliza a **base observada**, não considera o KNN meteorológico
anterior como se fosse medição. Cada valor realmente observado é preservado.
Somente ausências meteorológicas recebem ERA5 ou ERA5/Perez, inclusive as colunas
de umidade e radiações difusas que não tinham medições locais.
As variáveis elétricas mantêm o tratamento anterior, com os 25 dias estimados
por variável identificados no arquivo de origens.

A comparação com a estação foi restrita a **109 dias** com ao menos 80% de
cobertura original. Temperatura apresentou MAE de aproximadamente **0,69 °C**
e RMSE de **0,89 °C**. Isso mede concordância nos dias disponíveis, não o erro
real nos meses sem estação. Os erros das demais variáveis estão em
`comparacao_era5_estacao.csv`.

Foi identificada diferença de escala na irradiância horizontal: a razão entre
as medianas pública/local é de aproximadamente **10,70** nos dias comparados.
Não multiplicamos os valores da estação por dez sem comprovação de unidade ou
calibração. A direção observada permanece constante em 360°, e o vento público
representa altura de 10 m, que pode diferir da instalação local.

Por isso, há duas variantes finais:

- **`base_diaria_leopoldo_meteo_publica.csv`**: preserva a estação e preenche
  somente as lacunas. Recomendada para auditar a imputação e suas origens.
- **`base_diaria_leopoldo_meteo_homogenea.csv`**: mantém os mesmos valores
  elétricos e usa ERA5/Perez nas nove variáveis meteorológicas em todo o período.
  Permite experimentar uma fonte meteorológica uniforme, sem misturar as escalas
  da estação e da reanálise.

As duas têm o mesmo esquema de 13 colunas da referência australiana.
A completude não elimina as diferenças de representação espacial ou os erros
da reanálise. Os dados históricos ERA5 são retrospectivos; em uma previsão
operacional, a informação meteorológica precisa estar disponível na data de
emissão. A potência imputada continua excluída da avaliação de referência.

## Reprodução e arquivos

Executar `notebooks/04_brasil_meteorologia_publica.ipynb` para a fonte atual. A comparação histórica descrita neste texto é reproduzida em `notebooks/exploratorio/02_comparacao_meteorologia.ipynb`. As dependências estão em `requirements.txt`, na raiz do projeto.
A primeira consulta requer internet; depois o notebook reutiliza o cache e
confere seu SHA-256. Alterar coordenadas/período exige atualização explícita
do cache ou outra pasta, evitando reutilização silenciosa de dados de outro local.

- `data/external/era5/open_meteo_era5_2025.json`: resposta original da API.
- `data/external/era5/open_meteo_era5_2025_metadados.json`: consulta e hash do bruto.
- `data/interim/meteorologia/meteorologia_era5_horaria.csv`: variáveis horárias com fuso.
- `reports/exploratorio/meteorologia/processamento_meteorologia.json`: parâmetros da transformação.
- `meteorologia_era5_diaria.csv`: nove variáveis meteorológicas e medidas auxiliares.
- `origens_meteorologia_publica.csv`: fonte de cada célula e elegibilidade da potência.
- `relatorio_meteorologia_publica.csv`: faltantes antes/depois e dias por fonte.
- `comparacao_era5_estacao.csv`: erros e diferenças de escala nos dias disponíveis.
- `sensibilidade_azimute_era5.csv`: efeito da hipótese de orientação.
- `diagnostico_meteorologia_publica.png`: comparação visual com o tratamento anterior.

## Atribuição

Weather data by [Open-Meteo.com](https://open-meteo.com/), com dados Copernicus ERA5.
API e dados sob [CC BY 4.0](https://open-meteo.com/en/licence).
Modificações neste projeto: agregação em dias locais, reconstrução do contador de
chuva, transposição Perez e preenchimento de lacunas.

Referências do conjunto: [ERA5, Hersbach et al. (2020)](https://doi.org/10.1002/qj.3803)
e [Open-Meteo, Zippenfenig (2023)](https://doi.org/10.5281/zenodo.7970649).
