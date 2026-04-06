# EDA Harness

Репозиторий для разработки, тестирования и поэтапного доведения аналоговых блоков на `hdl21`, в первую очередь ОУ с `auto-zero` в `sky130`.

Этот документ описывает:
- что находится в проекте
- как в нём работать
- какие правила разработки обязательны
- как тестировать изменения
- где смотреть текущий статус и целевые требования

## Проект

Основной целевой блок сейчас:
- ОУ с `auto-zero` и низким остаточным offset в `sky130`

Базовая спецификация:
- [opamp_az_spec.md](/home/vadim/work/eda-harness/opamp_az_spec.md)

Текущее инженерное состояние:
- [track.md](/home/vadim/work/eda-harness/track.md)

Правила по компонентам, генераторам и структуре тестов:
- [hdl21.md](/home/vadim/work/eda-harness/hdl21.md)
- [tesing_guide.md](/home/vadim/work/eda-harness/tesing_guide.md)

Дополнительный служебный документ:
- [spice2xschem/README.md](/home/vadim/work/eda-harness/spice2xschem/README.md)

## Главный принцип работы

Проект ведётся **через тесты**.

Главное правило:
- **всё должно быть покрыто тестами**

Практический процесс всегда такой:
1. сформулировать требование как тест
2. запустить тест и получить реальную красную метрику
3. локализовать узкое место по этим метрикам
4. если нужно, уточнить или исправить тест
5. только после этого выдвигать гипотезу по схеме
6. проверять гипотезу автотестами
7. повторять цикл, пока метрика не станет зелёной

## Обязательные правила разработки

### 1. Сначала тест, потом схема

Перед любой серьёзной схемотехнической правкой должно быть ясно:
- какая метрика плохая
- каким тестом она измеряется
- какой ожидается выигрыш после правки

Если теста нет:
- сначала добавить тест

Если тест есть, но он не даёт однозначного сигнала:
- сначала улучшить тест

### 2. Узкие места выявляются только через метрики

Нельзя крутить размеры или topology “на ощущениях”.

Нужно:
- измерить текущее состояние
- зафиксировать реальные числа
- понять, где именно теряется качество:
  - gain
  - swing
  - drive
  - offset
  - pedestal
  - settling
  - leakage
  - corner robustness

Только после этого выбирать следующую гипотезу.

### 3. Тесты могут быть сломаны

Это ключевое правило проекта.

Всегда помнить:
- тесты могут быть неверно сформулированы
- измерительное окно может быть выбрано неправильно
- bench может искажать operating point
- loop-break может мерить не то, что кажется
- top-level budget test может случайно считать артефакты edge feedthrough как полезную ошибку

Если проблема долго не решается:
- **в первую очередь искать ошибку в тесте**

Это не исключение, а обязательная проверка.

### 4. Если результат не сходится с физической интуицией, сначала проверять measurement

Типовые примеры:
- слишком большой gain
- слишком странный phase margin
- неожиданный провал после “разумной” правки
- номинал хороший, а standalone блок показывает абсурд

В таких случаях сначала проверять:
- правильность fixture
- смысл измеряемой метрики
- окно измерения
- bias point
- sign convention

И только потом переделывать схему.

### 5. Разделять уровень компонента и уровень продукта

`components/`:
- reusable block tests
- `smoke`
- `contract`
- `char`

`tests/structural/...`:
- product-level budgets
- top-level requirements
- system-level checks

Нельзя смешивать:
- generic component characterization
- product-specific spec assertions

Подробности:
- [tesing_guide.md](/home/vadim/work/eda-harness/tesing_guide.md)

### 6. После каждой важной правки нужен быстрый прогон

Минимум:
- быстрый nominal screen
- затронутые budget tests

Нельзя делать серию схемных правок без промежуточных прогонов.

### 7. После nominal closure обязательно идти в corners

Нельзя считать устройство готовым только потому, что оно прошло `TT nominal`.

Минимум перед утверждением, что схема “почти готова”:
- nominal tests
- reduced `PVT`

Минимум перед tape-out:
- full `PVT`
- `MC`
- `PEX`
- post-layout verification

## Рекомендуемый рабочий цикл

Для любой проблемы:

1. Найти текущий тест или добавить новый.
2. Получить численную красную метрику.
3. Проверить, что тест меряет именно то, что нужно.
4. Снять debug-метрики и raw waveform, если есть сомнение.
5. Сформулировать 1 гипотезу.
6. Проверить гипотезу на автотестах.
7. Если гипотеза не сработала, зафиксировать это в [track.md](/home/vadim/work/eda-harness/track.md).
8. Если серия гипотез не помогает, вернуться к тесту и искать ошибку в measurement.

## Как читать проект

Рекомендуемый порядок:
1. [README.md](/home/vadim/work/eda-harness/README.md)
2. [opamp_az_spec.md](/home/vadim/work/eda-harness/opamp_az_spec.md)
3. [track.md](/home/vadim/work/eda-harness/track.md)
4. [tesing_guide.md](/home/vadim/work/eda-harness/tesing_guide.md)
5. [hdl21.md](/home/vadim/work/eda-harness/hdl21.md)

## Как тестировать

### Быстрые проверки

```bash
python3 -m unittest -v tests.structural.opamp_core.test_opamp_core__screen__fast_nominal
python3 -m unittest -v tests.structural.opamp_az_top.test_opamp_az_top__budget__precision_ppa
```

### Длинные, но полезные проверки

```bash
python3 -m unittest -v tests.structural.opamp_core.test_opamp_core__char__pvt
python3 -m unittest -v tests.structural.opamp_az_top.test_opamp_az_top__char__reduced_pvt
```

### Полный прогон

```bash
python3 -m unittest discover -s tests -v
```

## Что сейчас важно

На момент написания:
- `opamp_core` выглядит достаточно зрелым на nominal и лучше покрыт тестами
- `opamp_az_top` проходит top-level nominal budget
- главный blocker до tape-out сейчас в corner sensitivity `AZ`

Актуальные метрики и история экспериментов:
- [track.md](/home/vadim/work/eda-harness/track.md)

## Что нужно до tape-out

Минимальный путь:
1. довести схемотехнику до устойчивого reduced/full `PVT`
2. прогнать `MC`
3. сделать layout
4. прогнать `PEX`
5. повторить signoff-проверки post-layout

На сегодня tape-out readiness ещё нет.

## Индекс Markdown-документов

- [README.md](/home/vadim/work/eda-harness/README.md)
- [hdl21.md](/home/vadim/work/eda-harness/hdl21.md)
- [opamp_az_spec.md](/home/vadim/work/eda-harness/opamp_az_spec.md)
- [track.md](/home/vadim/work/eda-harness/track.md)
- [tesing_guide.md](/home/vadim/work/eda-harness/tesing_guide.md)
- [spice2xschem/README.md](/home/vadim/work/eda-harness/spice2xschem/README.md)
