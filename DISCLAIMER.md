# Aviso de risco e responsabilidade

Leia antes de instalar ou executar o Garimpo.

Este documento **não altera a licença**. O Garimpo é distribuído sob a licença
MIT (ver [LICENSE](LICENSE)), incluindo sua isenção de garantias e limitação de
responsabilidade. O texto abaixo explicita o que aquela isenção significa neste
projeto em particular.

## O que este projeto é

Um **experimento pessoal**, em estágio pre-alpha, para monitorar preço de
hardware em canais de oferta que a própria conta já acompanha, e avisar quando
um preço foge do histórico.

Não é produto, não é serviço, **não tem suporte** e não tem compromisso de
compatibilidade: interfaces, esquema de banco e comportamento mudam sem aviso.
Não há canal de atendimento, e issues ou mensagens podem simplesmente não ser
respondidas.

**Não é recomendado para uso geral.** Exige host ligado, número de Telegram
secundário e disposição para aceitar o risco descrito abaixo. Se você quer
alerta de promoção sem nada disso, use um serviço pronto — existem vários, e
qualquer um deles é escolha melhor.

## O que este projeto não faz

Declarações factuais sobre o código, verificáveis lendo o repositório:

- **Não contorna proteção de segurança.** Autentica pelo fluxo oficial do
  MTProto, com credenciais que você mesmo gera em my.telegram.org, na sua
  conta. Não há bypass de captcha, exploração de falha, nem uso de credencial
  alheia.
- **Não acessa conteúdo privado.** Lê apenas canais e grupos dos quais a conta
  configurada já é membro — o mesmo que você veria abrindo o aplicativo.
- **Não coleta dados de pessoas.** Não usa `GetParticipants` nem qualquer outro
  método de listagem de membros, não extrai contato, telefone ou perfil. O que
  entra no banco é preço, modelo, loja e o texto do anúncio.
- **Não envia nada nos grupos monitorados.** Não posta, não reage, não marca
  como lido, não entra em grupo sozinho.
- **Não redistribui o conteúdo lido.** O banco é local e o texto das mensagens
  nunca sai dele. A única saída de rede opcional é a telemetria comunitária,
  que vem **desligada**, precisa de endpoint configurado à mão, e envia apenas
  dado derivado — modelo, preço, loja e horário. Nunca texto de mensagem,
  nunca identificação de canal ou de pessoa.
- **Não usa IA.** Sem modelo, sem inferência, sem chave de API — parse é regex
  e catálogo curado à mão, decisão é estatística.

## Uso lícito é responsabilidade sua

O projeto se destina a acompanhar preço para decisão de compra própria. Usá-lo
para qualquer finalidade ilícita — assédio, vigilância de pessoas, coleta de
dados pessoais, fraude, violação de direito de terceiros — é contrário à
finalidade para a qual foi escrito e é responsabilidade exclusiva de quem o
fizer.

Os autores não têm como saber, controlar ou impedir o uso que terceiros fazem
do código, e não respondem por ele.

## Você é o operador

O Garimpo é software que roda **na sua máquina, com a sua conta, sob o seu
controle**. Quem executa o programa, escolhe as fontes, autentica a sessão e
opera o daemon é você. Os autores não hospedam serviço, não operam infraestrutura,
não intermedeiam o acesso e não têm visibilidade nenhuma sobre o seu uso.

## Risco de perda da conta de Telegram

O Garimpo autentica como **conta de usuário** via MTProto (userbot), não como bot
do BotFather.

Os [Content Licensing Terms](https://telegram.org/tos/content-licensing) do
Telegram licenciam acesso a dados para três categorias — Telegram Client,
Telegram Bot e Telegram Mini App. **O Garimpo não é nenhuma delas.** O
[API ToS §3.3](https://core.telegram.org/api/terms) exige ainda que apps que
acessam conteúdo de canais suportem sponsored messages, o que um processo sem
interface não tem como fazer.

**Existe risco real de restrição ou banimento permanente do número usado na
sessão.** Esse risco é seu, integralmente, e não é eliminado por nenhuma
precaução descrita na documentação.

Por isso o projeto exige, e não apenas recomenda:

- Usar um **número secundário**, dedicado, nunca o Telegram principal.
- Confirmar explicitamente esse entendimento digitando `secundario` no
  `garimpo login` antes de qualquer autenticação.

Análise detalhada da posição frente aos termos:
[docs/tos-compliance.md](docs/tos-compliance.md).

## Sem garantia de conformidade

Os autores **não garantem** que o uso do Garimpo esteja em conformidade com os
termos de serviço do Telegram, de qualquer varejista, ou de qualquer outro
terceiro — nem que essa avaliação permaneça válida, já que termos mudam sem
aviso e sem versionamento público.

Avaliar a legalidade e a adequação do uso na sua jurisdição, para a sua
finalidade, é responsabilidade sua. Nada neste repositório é aconselhamento
jurídico.

## Uso pessoal e não econômico

O projeto foi desenhado, e é documentado, para **uso pessoal e sem fim
econômico**.

Introduzir monetização — link de afiliado, comissão, revenda do feed, operação
como serviço para terceiros — muda a natureza jurídica do uso de forma
substantiva. No Brasil, entre outras coisas, remove a exceção do art. 4º, I da
LGPD, que dispensa da lei o tratamento feito "por pessoa natural para fins
exclusivamente particulares e não econômicos". Quem fizer isso assume um
conjunto de obrigações que este projeto não endereça e para o qual não oferece
apoio.

## Sem garantia sobre os dados

O Garimpo extrai preços de texto livre escrito por humanos. Parsers erram,
catálogos ficam desatualizados, mensagens são ambíguas e lojas anunciam
desconto falso.

Os alertas são **sinal estatístico, não recomendação de compra**, e podem estar
errados. Confira o anúncio original antes de comprar qualquer coisa. Os autores
não respondem por decisão de compra tomada com base em saída do programa.

## Isenção

NA MÁXIMA EXTENSÃO PERMITIDA PELA LEI APLICÁVEL, O SOFTWARE É FORNECIDO "COMO
ESTÁ", SEM GARANTIA DE QUALQUER NATUREZA. OS AUTORES E TITULARES DE DIREITOS
AUTORAIS NÃO RESPONDEM POR QUALQUER REIVINDICAÇÃO, DANO OU OUTRA
RESPONSABILIDADE — INCLUINDO, SEM LIMITAÇÃO, SUSPENSÃO OU BANIMENTO DE CONTA,
PERDA DE DADOS, PREJUÍZO FINANCEIRO OU DECISÃO DE COMPRA — DECORRENTE DO USO
DESTE SOFTWARE OU A ELE RELACIONADA.

Ao instalar ou executar o Garimpo você declara ter lido este aviso e assumido
os riscos descritos.
