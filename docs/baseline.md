# Baseline de preço: viés de seleção e âncora de varejo

Documento de trabalho. Nada aqui está implementado.

**Não implementar sem reler a seção 3.** A justificativa original não sobreviveu
a uma comparação casada por modelo de placa: o gap que motivava esta spec era
artefato de metodologia, não viés real.

---

## 1. O problema aparente

`price_history` é alimentado num único ponto (`pipeline.py`, no `_process`), com
`origin='telegram'`. Ou seja: **todo preço do baseline veio de mensagem que
alguém escolheu postar num grupo de ofertas.**

Isso é uma amostra de preços já descontados, não de preços de mercado. O
baseline responde "qual o desconto típico?", não "quanto custa o normal?" — e o
score compara oferta contra oferta, nunca contra varejo.

A coluna `origin` já existe na tabela e hoje tem um valor só. Ela foi
claramente prevista para isto.

## 2. Medição (2026-08-20, dados limpos, n=325)

| | Mediana | Mínimo |
|---|---|---|
| Baseline do Telegram, `rtx_5060` | R$ 2.189 | R$ 1.831 |
| Kabum, mesmo dia, 40 anúncios | R$ 2.834 | R$ 2.299 |

Gap de mediana: **-23%**. Persiste depois de remover a contaminação de modelo
errado e de máquina montada.

**Esta medição está errada em metodologia** — compara modelos de placa
diferentes dos dois lados. Mantida aqui porque foi ela que motivou a spec, e a
seção 3 mostra o que aconteceu ao refazê-la corretamente.

## 3. Por que esta spec provavelmente não deve ser implementada

A justificativa original não sobreviveu a uma comparação honesta.

O gap de -23% da seção 2 compara a mediana do grupo contra a mediana de todos
os anúncios da Kabum — **modelos diferentes dos dois lados**. Uma Palit
Infinity 2 de entrada e uma ASUS TUF não custam o mesmo, e nenhum viés
estatístico é necessário para explicar a diferença.

Refazendo casado por marca + linha de placa, em 234 ofertas de `rtx_5060`:

| marca + linha | grupo | Kabum | delta |
|---|---|---|---|
| msi cyclone | 2.074 | 2.600 | -20,2% |
| zotac twin edge | 2.230 | 2.834 | -21,3% |
| gigabyte windforce | 2.112 | 2.600 | -18,7% |
| gigabyte eagle | 2.282 | 2.800 | -18,5% |
| asus dual | 2.199 | 2.600 | -15,4% |
| msi shadow 2x | 2.136 | 2.499 | -14,5% |
| msi ventus 3x | 2.299 | 2.599 | -11,5% |
| asus prime | 2.500 | 2.800 | -10,7% |
| palit infinity 2 | 2.107 | 2.299 | -8,4% |
| msi ventus 2x | 2.249 | 2.399 | -6,3% |
| gigabyte gaming oc | 2.369 | 2.483 | -4,6% |

O grupo é mais barato em **todas as onze linhas**. E ofertas acima do mesmo SKU
na Kabum são **3% (6 de 234)**, não os 12% que a comparação cruzada sugeria.

Ou seja: o baseline do Telegram não está sistematicamente enviesado para baixo
de forma enganosa — ele reflete que oferta de grupo é genuinamente mais barata
que prateleira. E "isto é mais barato que 97% do que circulou" continua sendo a
pergunta certa para quem compra de grupo de oferta.

**O que sobra para justificar um coletor:**

1. 3% de oferta acima do preço de varejo do mesmo modelo. Marginal.
2. Deriva absoluta: se o mercado inteiro subir 20%, o baseline sobe junto e
   nada parece caro. Real, mas raro e lento.

Ambos são cobertos pela alternativa da seção 5, que custa meia hora e nenhuma
requisição de rede. **Implementar o coletor não se justifica hoje.** Esta spec
fica registrada para o caso de a situação mudar — por exemplo, se o parse
passar a cobrir muitas categorias e a curadoria manual deixar de escalar.

## 4. Desenho

### Fontes

Só duas, e por motivo de ToS, não de conveniência:

- **Kabum** — `robots.txt` permite `/produto/` e `/busca/{termo}` (sem query
  string). O preço vem em JSON dentro de `<script id="__NEXT_DATA__">` no HTML
  server-renderizado: objetos com `name`, `price` e `priceWithDiscount`. Não
  precisa de headless browser. Verificado: `GET /busca/rtx-5060` → 200, 101
  produtos no payload.
- **Shopee** — único `robots.txt` que declara `Crawl-delay: 1` para UA
  genérico. Tolerância declarada.

**Não incluir Terabyte nem Magazine Luiza.** Ambas bloqueiam até o próprio
`robots.txt` com bot management ativo (Cloudflare challenge / Akamai). Passar
disso exigiria headless browser e possivelmente proxy residencial, o que muda a
conduta de "raspagem educada" para "evasão de proteção anti-bot" — linha
jurídica pior que a do Telegram, por um ganho marginal.

### Comportamento

- Uma passada por dia. 23 modelos × 2 lojas ≈ 46 requisições/dia.
- `User-Agent` identificando o projeto e a natureza pessoal do uso.
- Respeitar `Crawl-delay` onde declarado; alguns segundos entre requisições
  onde não houver.
- `If-Modified-Since` / `ETag` quando o servidor oferecer.
- Falha de uma loja não derruba a outra nem o daemon.

### Gravação

`origin='retail'`, com a loja em `store`. **Nunca** misturar com
`origin='telegram'` no mesmo cálculo.

### Uso no score

Aqui está a decisão de projeto que ainda não está tomada, e que não deve ser
tomada no escuro:

- **Opção A** — baseline computado sobre `origin='retail'`, e a oferta do
  Telegram pontuada contra ele. Responde "quanto isto é mais barato que a
  prateleira?".
- **Opção B** — manter o baseline atual e usar o varejo apenas como **teto de
  sanidade**: sinalizar quando uma "oferta" está acima do varejo. Muito mais
  barato, cobre os 3% de desconto duvidoso, e não mexe na calibração já validada.

**Opção B, se algum dia.** A calibração atual (17 critical / 80 normal em ~60 dias)
foi validada com dados reais; trocar o denominador de uma vez descarta essa
validação sem necessidade.

Nota sobre qual número usar como âncora: a mediana entre anúncios da Kabum
(R$ 2.834) inclui modelos premium e não é o que um comprador paga. O mínimo ou
um percentil baixo entre anúncios do mesmo modelo é a referência mais honesta.

## 5. Alternativa de 30 minutos

Antes de escrever coletor: `gpu.json` já tem `price_range` nos 23 modelos e
`msrp_brl` em 3. Preencher à mão um `street_price_brl` para os 23 dá âncora
absoluta imediata, sem código, sem rede e sem qualquer questão de ToS.

Fica desatualizado, e é exatamente isso que o coletor automatiza. Mas cobre os
dois casos da seção 3 no mesmo dia, e por isso **é o caminho recomendado**.

## 6. Aceite

- Coletor roda uma vez, grava `origin='retail'` para os modelos do catálogo, e
  não toca em nenhuma linha `origin='telegram'`.
- Baseline computado sobre `origin='telegram'` permanece idêntico ao de antes
  do coletor (garante que nada vazou entre as origens).
- Oferta acima do preço de varejo do mesmo modelo é sinalizada.
- Loja fora do ar não derruba o processo nem polui o histórico com preço zero.
- `robots.txt` de cada loja é conferido no momento da implementação — os desta
  spec foram lidos em 2026-08-20 e mudam sem aviso.
